"""
The tsnet.simulation.initialize contains functions to
1. Initialize the list containing numpy arrays for velocity and head.
2. Calculate initial conditions using Epanet engine.
3. Calculate D-W coefficients based on initial conditions.
4. Calculate demand coefficients based on initial conditions.

"""
import math
import logging
import warnings
from typing import Literal, TypeAlias

import wntr
import numpy as np
import pandas as pd

from ..utils import calc_parabola_vertex
from ..network.model import TransientModel
from .custom_exceptions import (
    InitialConditionError,
    InitialConditionTimeError,
    InvalidEngineError,
    UnsupportedPumpCurveError,
    ResultNotFoundError,
    ResultNonFiniteError
)
from .custom_warnings import ExcessiveFrictionWarning, InitializationWarning
from .constants import (
    ST_GRAVITY,
    KINEMATIC_VISCOSITY,
    DW_HEAD_TOLERANCE,
    DW_VELOCITY_TOLERANCE,
    DW_ROUGHNESS_EPSILON,
    DW_COEFF_MAX,
    DW_COEFF_DEFAULT,
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

Engine: TypeAlias = Literal["DD", "PDD"]
WNTRSimulationResults: TypeAlias = wntr.sim.results.SimulationResults
Pipe = TypeAlias = wntr.network.elements.Pipe

# ------------------------
# Private helper functions
# ------------------------

def _calculate_roughness_coefficient(
        pipe: Pipe,
        v_init: float,
        hl_init: float,
        dw_coeff_max: float = DW_COEFF_MAX,
        dw_coeff_default: float = DW_COEFF_DEFAULT) -> None:
    """Calculate the D-W roughness coefficient based on initial conditions.

    Parameters
    ----------
    pipe : Pipe
        WNTR's Pipe object
    v_init : float
        Initial flow velocity in the pipe
    hl_init : float
        Initial head loss in the pipe

    Note
    ----
    The D-W roughness coefficient is calculated using the formula:
        roughness = hl / (L/D) / (v^2/2/g)
    The function modifies the pipe object in place, setting the roughness and 
    roughness_height attributes.
    """

    if abs(v_init) >= DW_VELOCITY_TOLERANCE and hl_init >= DW_HEAD_TOLERANCE:
        roughness = hl_init / (pipe.length/pipe.diameter) / (v_init**2/2/ST_GRAVITY)
    else:
        roughness = DW_ROUGHNESS_EPSILON
    if roughness > dw_coeff_max:
        warnings.warn(
            f"{pipe.name}: Darcy-Weisbach friction coefficient "
            f"{pipe.roughness:.4f} is unusually large; "
            f"setting it to {dw_coeff_default:.2f}.",
            ExcessiveFrictionWarning,
            stacklevel=2,
        )
        roughness = dw_coeff_default
    if roughness!= 0:
        roughness_height = max(
            10**(-1/1.8/math.sqrt(roughness)) - 6.9/pipe.initial_Re,
            0
        )
    else:
        roughness_height = 0.0
    pipe.roughness_height = roughness_height
    pipe.roughness = roughness


def _calculate_demand_coefficient(
    pipe: Pipe,
    start_demand: float,
    end_demand: float,
    start_head: float,
    end_head: float,
) -> None:
    """Calculate demand coefficients for a pipe's endpoint nodes.

    The demand coefficient is calculated according to

    .. math::

        C_d = \\frac{Q_d}{\\sqrt{H}}

    where ``Q_d`` is the demand discharge and ``H`` is the pressure
    head at the node.

    Parameters
    ----------
    pipe
        Pipe whose endpoint nodes are being initialized.
    start_demand : float
        Demand at the start node [m³/s].
    end_demand : float
        Demand at the end node [m³/s].
    start_head : float
        Pressure head at the start node [m].
    end_head : float
        Pressure head at the end node [m].
    """
    def _demand_coefficient(demand: float, pressure_head: float) -> float:
        """
        Calculate a pressure-dependent demand coefficient, [m^3/s/(m H20)^(1/2)]
        """
        if pressure_head <= 0.0 or not np.isfinite(pressure_head):
            return 0.0
        if not np.isfinite(demand):
            return 0.0
        return demand / math.sqrt(pressure_head)

    pipe.start_node.demand_coeff = _demand_coefficient(
        demand=start_demand,
        pressure_head=start_head,
    )
    pipe.end_node.demand_coeff = _demand_coefficient(
        demand=end_demand,
        pressure_head=end_head,
    )


def _allocate_result_arrays(tm: TransientModel, number_of_steps: int) -> None:
    """Allocate arrays used to store transient simulation results.
    Adds the following attributes to each pipe and node in the TransientModel:
    - Pipe:
        - start_node_head
        - start_node_velocity
        - start_node_flowrate
        - end_node_head
        - end_node_velocity
        - end_node_flowrate
    - Node:
        - demand_discharge
        - emitter_discharge
        
    Parameters
    ----------
    tm : tsnet.network.model.TransientModel
        The TransientModel to which the result arrays will be added.
    number_of_steps : int
        The number of time steps in the simulation, used to determine the size of 
        the arrays.
        
    Note: This function modifies the TransientModel in place. TransientModel itself
    inherits from WNTR's WaterNetworkModel. TransientModel is a subclass that enables
    running transient simulations and storing additional attributes for each pipe and
    node.
    """
    for _, pipe in tm.pipes():
        pipe.start_node_head = np.zeros(number_of_steps)
        pipe.start_node_velocity = np.zeros(number_of_steps)
        pipe.start_node_flowrate = np.zeros(number_of_steps)
        pipe.end_node_head = np.zeros(number_of_steps)
        pipe.end_node_velocity = np.zeros(number_of_steps)
        pipe.end_node_flowrate = np.zeros(number_of_steps)
    for _, node in tm.nodes():
        node.demand_discharge = np.zeros(number_of_steps)
        node.emitter_discharge = np.zeros(number_of_steps)


def _apply_initial_leaks(tm: TransientModel, t0: float) -> None:
    """Apply configured node leaks at the initial simulation time.
    
    Parameters
    ----------
    tm : tsnet.network.model.TransientModel
        The TransientModel containing the nodes to which leaks will be applied.
    t0 : float
        The initial simulation time at which the leaks will be applied.
    """
    for _, node in tm.nodes():
        if node._leak_status: #pylint: disable=protected-access (WNTR's design issue)
            node.add_leak(
                tm,
                area=node.emitter_coeff / math.sqrt(2.0 * ST_GRAVITY),
                discharge_coeff=1.0,
                start_time=t0,
            )


def _run_steady_state(tm: TransientModel, engine: Engine, *, t0: float) -> WNTRSimulationResults:
    """Run EPANET to obtain the hydraulic state at ``t0``.
    
    The EPANET simulation duration is temporarily set to ``t0`` so that
    the returned hydraulic results include the state at the requested
    initial simulation time. The model's original simulation duration is
    restored after the simulation.

    Parameters
    ----------
    tm: TransientModel
        Transient water-network model to initialize.
    engine: Engine
        Hydraulic demand model to use for the steady-state calculation.
    t0: float
        Initial time of the transient simulation, in seconds.

    Returns
    -------
    WNTRSimulationResults
        EPANET steady-state results used to initialize the transient
        simulation.

    Raises
    ------
    InitialConditionError
        If ``t0`` is negative, the EPANET steady-state simulation fails,
        or the simulation returns no node pressure results.
    """
    if t0 < 0.0:
        raise InitialConditionError(
            f"Initial simulation time must be non-negative, got {t0!r}."
        )
    original_duration = tm.options.time.duration
    try:
        tm.reset_initial_values()
        tm.options.hydraulic.demand_model = engine
        tm.options.time.duration = t0
        simulator = wntr.sim.EpanetSimulator(tm)
        results = simulator.run_sim()
        if results.node["pressure"].empty:
            raise InitialConditionError(
                "EPANET steady-state simulation returned no "
                "node pressure results."
            )
        return results
    except (RuntimeError, ValueError, OSError) as exc:
        raise InitialConditionError(
            "EPANET steady-state simulation failed using "
            f"the {engine!r} demand model at t0={t0!r} s."
        ) from exc
    finally:
        # Restore the duration belonging to the caller's model.
        tm.options.time.duration = original_duration


def _store_initial_node_conditions(tm: TransientModel, head: pd.Series) -> None:
    """Store initial hydraulic head at each node."""
    for _, node in tm.nodes():
        try:
            node.initial_head = float(head[node.name])
        except KeyError as exc:
            raise InitialConditionError(
                f"No initial head was found for node {node.name!r}."
            ) from exc


def _store_initial_link_conditions(tm: TransientModel, flowrate: pd.Series) -> None:
    """Store initial flow rate at each link."""
    for _, link in tm.links():
        try:
            link.initial_flow = float(flowrate[link.name])
        except KeyError as exc:
            raise InitialConditionError(
                f"No initial flow rate was found for link {link.name!r}."
            ) from exc


def _store_node_discharge(
    pipe: Pipe,
    start_head: float,
    end_head: float,
) -> None:
    """Store demand and emitter discharge at junction endpoints.

    For each endpoint of ``pipe`` that is a junction, calculate the emitter
    and demand discharge from the corresponding hydraulic head and store the
    results in the endpoint node's discharge arrays.

    The discharge is calculated as::

        discharge = coefficient * sqrt(head)

    Non-junction endpoints are ignored.

    Parameters
    ----------
    pipe : Pipe
        Pipe whose start and end nodes are evaluated.
    start_head : float
        Hydraulic head at the start node.
    end_head : float
        Hydraulic head at the end node.

    Returns
    -------
    None
        The function updates the endpoint nodes in place and does not return
        a value.

    Notes
    -----
    The function assumes that ``start_head`` and ``end_head`` are valid for
    the square-root calculation. In particular, negative heads will result
    in ``NaN`` when using NumPy's ``sqrt``.
    """
    start_node = pipe.start_node
    if start_node.node_type == "Junction":
        sqrt_head = math.sqrt(start_head)
        start_node.emitter_discharge[0] = (
            start_node.emitter_coeff * sqrt_head
        )
        start_node.demand_discharge[0] = (
            start_node.demand_coeff * sqrt_head
        )
    end_node = pipe.end_node
    if end_node.node_type == "Junction":
        sqrt_head = math.sqrt(end_head)
        end_node.emitter_discharge[0] = (
            end_node.emitter_coeff * sqrt_head
        )
        end_node.demand_discharge[0] = (
            end_node.demand_coeff * sqrt_head
        )


def _get_result_value(
        data: pd.Series,
        name: str, 
        default: float | None = None) -> float:
    """Return a finite result value from a pandas Series.

    The value associated with ``name`` is retrieved from ``data``. If the
    field is absent or its value is not finite, ``default`` is returned when
    one is provided. Otherwise, an appropriate exception is raised.

    Parameters
    ----------
    data : pandas.Series
        Series containing the result values.
    name : str
        Name of the result field to retrieve.
    default : float or None, default=None
        Value to return when ``name`` is absent or its associated value is
        not finite. If ``None``, a missing field raises
        :class:`ResultNotFoundError` and a non-finite value raises
        :class:`ResultNonFiniteError`.

    Returns
    -------
    float
        The finite result value associated with ``name``, or ``default`` when
        the value is missing or non-finite and a default is provided.

    Raises
    ------
    ResultNotFoundError
        If ``name`` is not present in ``data`` and ``default`` is ``None``.
    ResultNonFiniteError
        If the value associated with ``name`` is not finite and ``default``
        is ``None``.
    """
    try:
        value = data[name]
    except KeyError as exc:
        if default is not None:
            value = default
        else:
            raise ResultNotFoundError(
                f"Result for field {name!r} could not be found."
            ) from exc
    if not np.isfinite(value):
        if default is not None:
            value = default
        else:   
            raise ResultNonFiniteError(
                f"Result for field {name!r} has a non-finite value."
            )
    return float(value)


def _initialize_pipe(
    pipe,
    head,
    flowrate,
    velocity,
    demand,
) -> None:
    """Calculate and store initial conditions for one pipe."""

    try:
        start_head = head[pipe.start_node_name]
        end_head = head[pipe.end_node_name]
        initial_flow = flowrate[pipe.name]
        initial_velocity = velocity[pipe.name]
    except KeyError as exc:
        raise InitialConditionError(
            f"Missing EPANET result required to initialize "
            f"pipe {pipe.name!r}."
        ) from exc

    number_of_points = pipe.number_of_segments + 1
    
    logger.debug(
        f"Pipe {pipe.name}: start_head={start_head:.2f}, end_head={end_head:.2f}, initial_flow={initial_flow:.2f}, initial_velocity={initial_velocity:.2f}")

    # Initial velocity is assumed constant along the pipe.
    velocity_profile = np.full(
        number_of_points,
        np.sign(initial_flow) * initial_velocity,
        dtype=float,
    )

    # Old initialization with list comprehension
    #head_profile = np.array([
    #    start_head +
    #    i* ((end_head-start_head) / (number_of_points-1))
    #    for i in range(number_of_points
    #)])
    
    # Linearly interpolate hydraulic head between pipe endpoints.
    head_profile = np.linspace(
        start_head,
        end_head,
        number_of_points,
        dtype=float,
    )
    
    pipe.initial_head = head_profile
    pipe.initial_velocity = velocity_profile
    pipe.initial_Re = abs(
        velocity_profile[0] * pipe.diameter / KINEMATIC_VISCOSITY
    )

    # Store endpoint conditions.
    pipe.start_node_velocity[0] = velocity_profile[0]
    pipe.end_node_velocity[0] = velocity_profile[-1]
    pipe.start_node_head[0] = head_profile[0]
    pipe.end_node_head[0] = head_profile[-1]
    pipe.start_node_flowrate[0] = velocity_profile[0] * pipe.area
    pipe.end_node_flowrate[0] = velocity_profile[-1] * pipe.area

    try:
        start_node_elevation = pipe.start_node.elevation
    except AttributeError:
        # If node does not contain the elevation attribute, assume 1.0
        start_node_elevation = 1.0
        
    try:
        end_node_elevation = pipe.end_node.elevation
    except AttributeError:
        # If node does not contain the elevation attribute, assume 1.0
        end_node_elevation = 1.0
        
    start_pressure_head = start_head - start_node_elevation
    end_pressure_head = end_head - end_node_elevation

    # Find demands at the beginning and at the end of the pipe.
    # In case the demand cannot be found, assume that the demand is zero.
    start_demand = _get_result_value(
        demand,
        pipe.start_node_name,
        default = 0.0
    )
    end_demand = _get_result_value(
        demand,
        pipe.end_node_name,
        default = 0.0
    )
    _calculate_demand_coefficient(
        pipe,
        start_demand=start_demand,
        end_demand=end_demand,
        start_head=start_pressure_head,
        end_head=end_pressure_head,
    )

    _store_node_discharge(pipe, start_pressure_head, end_pressure_head)

    head_loss = abs(start_head - end_head)

    _calculate_roughness_coefficient(
        pipe,
        v_init=velocity_profile[0],
        hl_init=head_loss,
        dw_coeff_max=DW_COEFF_MAX,
        dw_coeff_default=DW_COEFF_DEFAULT
    )


def pump_operating_points(tm: TransientModel) -> TransientModel:
    """Calculate pump operating points and curve coefficients.

    Parameters
    ----------
    tm : TransientModel
        Transient model containing pumps.

    Returns
    -------
    TransientModel
        The updated transient model.

    Raises
    ------
    UnsupportedPumpCurveError
        If a pump curve does not contain one or three points.
    """
    for _, pump in tm.pumps():
        curve = pump.get_pump_curve()
        points = curve.points
        # single point pump curve
        if len(points) == 1:
            flow, head = points[0]
            points.extend(
                [
                    (0.0, 1.33 * head),
                    (2.0 * flow, 0.0),
                ]
            )
        elif len(points) != 3:
            raise UnsupportedPumpCurveError(
                f"Pump {pump.name!r} has {len(points)} curve points. "
                "TSNet supports only one-point or three-point pump curves."
            )
        operating_point = (
            pump.initial_flow,
            abs(
                pump.end_node.initial_head
                - pump.start_node.initial_head
            ),
        )
        closest_point = min(
            points,
            key=lambda point: (
                (point[0] - operating_point[0]) ** 2
                + (point[1] - operating_point[1]) ** 2
            ),
        )
        points.remove(closest_point)
        points.append(operating_point)
        pump.curve_coef = calc_parabola_vertex(points)
    return tm


def initialize(tm: TransientModel, t0: float, engine: Engine='DD') -> TransientModel:
    """Initial Condition Calculation.
    
    The initialization performs the following operations:
    
    1. Allocate arrays used to store transient head, velocity, and flow-rate
       results at pipe endpoints.
    2. Allocate node arrays for demand and emitter discharge.
    3. Apply configured leaks.
    4. Run an EPANET steady-state simulation.
    5. Store the initial head and flow conditions.
    6. Interpolate initial head and velocity along each pipe.
    7. Calculate demand coefficients.
    8. Calculate Darcy-Weisbach friction coefficients.
    9. Determine pump operating points and corresponding pump coefficients.

    Parameters
    ----------
    tm : tsnet.network.model.TransientModel
        Simulated network
    t0 : float
        time to calculate initial condition
    engine : Engine
        steady state calculation engine:
        DD: demand driven;
        PDD: pressure dependent demand,
        by default DD

    Returns
    -------
    tm : tsnet.network.model.TransientModel
        Network with updated parameters
    """

    engine = engine.upper()
    if engine not in {"DD", "PDD"}:
        raise InvalidEngineError(
            f"Unknown initial-condition engine {engine!r}. "
            "Expected 'DD' or 'PDD'."
        )
    number_of_steps = int(tm.simulation_period/tm.time_step) # Total time steps
    
    logger.info(
        "Initializing transient model with %d simulation time steps.",
        number_of_steps,
    )
    
    # Allocate start and end node head, velocity and flowrate numpy arrays for
    # each pipe and demand and emitter discharge arrays for each node; then attach
    # them to the TransientModel's node and pipe attributes
    _allocate_result_arrays(tm, number_of_steps)
    # Add leaks at the initial time step if configured
    _apply_initial_leaks(tm, t0)
    # Run EPANET steady-state simulation to calculate initial conditions
    results = _run_steady_state(tm, engine, t0=t0)
    
    try:
        head = results.node["head"].loc[t0]
        flowrate = results.link["flowrate"].loc[t0]
        velocity = results.link["velocity"].loc[t0]
        demand = results.node["demand"].loc[t0]
    except KeyError as exc:
        raise InitialConditionTimeError(
            f"Initial-condition time t0={t0!r} is not available "
            "in the EPANET results."
        ) from exc

    _store_initial_node_conditions(tm, head)
    _store_initial_link_conditions(tm, flowrate)

    for _, pipe in tm.pipes():
        _initialize_pipe(
            pipe=pipe,
            head=head,
            flowrate=flowrate,
            velocity=velocity,
            demand=demand,
        )

    pump_operating_points(tm)
    return tm

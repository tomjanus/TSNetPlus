"""
The tsnet.kernels.numba.simulator module contains function to perform
the workflow of reading, discretizing, initialization, and transient
simulation for the given .inp file.

This is the modification of the original Python implementation to work
with numba just in time (JIT) compiler

Changes relative to the reference implementation
------------------------------------------------

1.  The Numba JIT compiler moves the scalar Python loops in the three inner node  functions of 
    Solver.py (for steady, unsteady, and quasisteady) into a Numba-compiled function.
    
2.  Gather Pipe-property;  The connected-pipe and endpoint indices are precomputed once. 
    At every timestep, _gather() uses those saved indices to retrieve the current H, V, dVdt and dVdx values. This avoids repeatedly calculating abs(i), np.sign(i) and endpoint mappings.

3.  Buffer reuses; 
HN, VN are allocated once per pipe at startup and overwritten each timestep instead of being 
re-created with np.zeros_like every step.

"""
from __future__ import print_function
import warnings
import logging
from datetime import datetime
from typing import Literal, TypeAlias
import math
import pickle
import numpy as np
from rich.logging import RichHandler
from ...network import  topology
from .single import inner_pipe, left_boundary, right_boundary
from ...utils import valve_curve
from ...utils import calc_parabola_vertex


KernelType: TypeAlias = Literal['python', 'numba', 'cython']

logger = logging.getLogger(__name__)

handler = RichHandler()
warnings_logger = logging.getLogger("py.warnings")
warnings_logger.addHandler(handler)
logging.captureWarnings(True)

# --------------------------------------------------------------
# Private helper functions
# --------------------------------------------------------------

def _pump_points(link, ts):
    """Replicate the original pump-point scaling compactly."""
    points = link.get_pump_curve().points
    po = link.operation_rule[ts]
    return [(i * po, j * po * po) for (i, j) in points]


def _valve_coef(link, ts):
    if link.operating:
        return valve_curve(link.operation_rule[ts] * 100.0, link.valve_coeff)
    if link.initial_status.name == 'Open':
        return valve_curve(100.0, link.valve_coeff)
    return valve_curve(0.0, link.valve_coeff)

# ---------------------------------------------------------------------------
# Fast result recording
# ---------------------------------------------------------------------------
def _record(pipe, ts, HN_p, VN_p,
            record_velocity, record_flowrate, record_demand,
            do_start=True, do_end=True,
            start_is_junction=None, end_is_junction=None):
    #Write the current time-step results into the pipe / node arrays.
    # Uses math.sqrt on scalars (Python floats) —  faster than np.sqrt(scalar).

    
    if do_start:
        h0 = HN_p[0]
        pipe.start_node_head[ts] = h0
        if record_velocity:
            pipe.start_node_velocity[ts] = VN_p[0]
        if record_flowrate:
            pipe.start_node_flowrate[ts] = VN_p[0] * pipe.area
        if record_demand:
            sn = pipe.start_node
            ####
            ###
            is_j = (start_is_junction if start_is_junction is not None
                    else getattr(sn, 'transient_node_type', None) == 'Junction')
            if is_j:
                hh = h0 - sn.elevation
                if hh > 0.0:
                    s = math.sqrt(hh)
                    sn.demand_discharge[ts] = sn.demand_coeff * s
                    sn.emitter_discharge[ts] = sn.emitter_coeff * s
                else:
                    sn.demand_discharge[ts] = 0.0
                    sn.emitter_discharge[ts] = 0.0

    if do_end:
        hn = HN_p[-1]
        pipe.end_node_head[ts] = hn
        if record_velocity:
            pipe.end_node_velocity[ts] = VN_p[-1]
        if record_flowrate:
            pipe.end_node_flowrate[ts] = VN_p[-1] * pipe.area
        if record_demand:
            en = pipe.end_node
            is_j = (end_is_junction if end_is_junction is not None
                    else getattr(en, 'transient_node_type', None) == 'Junction')
            if not is_j:
                return
            hh = hn - en.elevation
            if hh > 0.0:
                s = math.sqrt(hh)
                en.demand_discharge[ts] = en.demand_coeff * s
                en.emitter_discharge[ts] = en.emitter_coeff * s
            else:
                en.demand_discharge[ts] = 0.0
                en.emitter_discharge[ts] = 0.0

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def MOCSimulator(tm, results_obj='results', friction='steady'):
    """ MOC Main Function

    Parameters
    ----------
    tm : tsnet.network.model.TransientModel
        Network
    results_obj: string, optional
        the name of the results file, by default 'results'
    friction: string, optional
        friction model, e.g., 'steady', 'quasi-steady', 'unsteady',
        by default 'steady'
    kernel: KernelType, optional
        computational kernel used by MOC simulator. Three kernels are
        available: 'python', 'numba', 'cython'

    Returns
    ------
    tm : tsnet.network.model.TransientModel
            Simulated network
    """
    
    logger.info("Running NUMBA MOCSimulator...")
    
    record_velocity=True,
    record_flowrate=True,
    record_demand=True

    if friction not in ('steady', 'quasi-steady', 'unsteady'):
        raise ValueError(
            "friction must be 'steady', 'quasi-steady' or 'unsteady'")

    # ---------- topology ----------
    links1, links2, utype, dtype = topology(tm)
    logger.debug("Network Topology Solved.")

    dt = tm.time_step
    tn = int(tm.simulation_period / tm.time_step)
    Hb = 10.3  # barometric head

    # ---------- gather pipes ----------
    pipes = [pipe for _, pipe in tm.pipes()]
    num_pipes = tm.num_pipes

    # ---------- preallocate state buffers ----------
    # results from last time step
    H  = [None] * num_pipes
    V  = [None] * num_pipes
    # results at current time step
    HN = [None] * num_pipes
    VN = [None] * num_pipes
    # results for local and convective
    #  instantaneous acceleration
    dVdt = [None] * num_pipes
    dVdx = [None] * num_pipes

    for pipe in pipes:
        pn = pipe.id - 1
        H[pn]  = np.array(pipe.initial_head, dtype=np.float64, copy=True)
        V[pn]  = np.array(pipe.initial_velocity, dtype=np.float64, copy=True)
        HN[pn] = np.zeros_like(H[pn])
        VN[pn] = np.zeros_like(V[pn])
        if friction == 'unsteady':
            dVdt[pn] = np.zeros_like(V[pn])
            dVdx[pn] = np.diff(V[pn]) / (pipe.length / pipe.number_of_segments)
        else:
            dVdt[pn] = np.zeros_like(V[pn])
            dVdx[pn] = np.zeros_like(V[pn][:-1])

    # determine which node of the adjacent pipe should be call:
    # if the adjacent pipe is entering the junction, then -2
    # if the adjacent pipe is leaving the junction, then 1
    a_map = {1: -2, -1: 1}
    b_map = {1: -1, -1: 0}
    # for both its upstream (links1) and downstream (links2) neighbours.
        # These only depend on the topology, so compute once.

    def _gather_spec(link_list):
        # returns (np.array of pipe indices, np.array of node indices, np.array of dVdx indices)
        if not link_list or link_list == ['End']:
            return None
        pidx = np.array([abs(i) - 1 for i in link_list], dtype=np.intp)
        sign = np.array([1 if i > 0 else -1 for i in link_list], dtype=np.intp)
        n_idx = np.array([a_map[s] for s in sign], dtype=np.intp)
        b_idx = np.array([b_map[s] for s in sign], dtype=np.intp)
        return pidx, n_idx, b_idx, sign

    topo1 = [_gather_spec(links1[pn]) for pn in range(num_pipes)]
    topo2 = [_gather_spec(links2[pn]) for pn in range(num_pipes)]

    def _gather(pipe_state, spec, use_b=False):
        if spec is None:
            return []
        pidx, n_idx, b_idx, _sign = spec
        idx = b_idx if use_b else n_idx
        # Can't use fancy numpy indexing because each pipe has its own array
        # (arrays have different lengths), so we do a plain list comprehension.
        # But we avoid the np.sign / abs calls the original had to do every step.
        return [pipe_state[p][i] for p, i in zip(pidx, idx)]

    # ---------- initialise surge tanks / air chambers / pulse nodes ----------
    for _, node in tm.nodes():
        if node.pulse_status:
            node.base_demand_coeff = node.demand_coeff
        ttype = node.transient_node_type
        if ttype in ('SurgeTank', 'Chamber'):
            if ttype == 'Chamber':
                m = 1.2
                Ha = node.initial_head - node.water_level + Hb
                Va = node.tank_shape[0] * (node.tank_height - node.water_level)
                node.air_constant = Ha * Va ** m
                node.tank_shape.insert(2, node.air_constant)
            else:  # SurgeTank
                node.water_level = node.initial_head
                node.tank_shape.insert(1, node.water_level)
            node.water_level_timeseries = np.zeros(tn)
            node.tank_flow_timeseries = np.zeros(tn)
            node.water_level_timeseries[0] = node.water_level

    tt = ['x', 0]
    starttime = datetime.now()

    # ===================================================================
    # # Start Calculation
    # ===================================================================
    for ts in range(1, tn):
        if ts == 2:
            for pipe in pipes:
                diff1 = pipe.start_node_head[1] - pipe.start_node_head[0]
                diff2 = pipe.end_node_head[1] - pipe.end_node_head[0]
                if abs(diff1) > 0.5:
                    logger.debug(
                        'Initial condition discrepancy of pressure '
                        '(%.4f m) on the %s node'
                        % (diff1, pipe.start_node.name)
                    )
                if abs(diff2) > 0.5:
                    logger.debug(
                        'Initial condition discrepancy of pressure '
                        '(%.4f m) on the %s node'
                        % (diff2, pipe.end_node.name)
                    )
        if ts == 3:
            per = (datetime.now() - starttime) / 2.0
            logger.debug('Estimated simulation time %s' % (per * tn))

        t = ts * dt
        tt.append(t)

        # Per-step node updates
        # for burst node: emitter_coeff = burst_coeff[ts]
        for _, node in tm.nodes():
            if node.burst_status:
                node.emitter_coeff = node.burst_coeff[ts]
            if node.pulse_status:
                node.demand_coeff = node.base_demand_coeff \
                                    * (1.0 + node.pulse_coeff[ts])

        # The fast version reuses the existing HN and VN arrays instead of creating new arrays every timestep.
        # Before reuse, it resets their values to zero with .fill(0.0).
        # The inner-node kernel overwrites all middle elements.
        # The boundary functions overwrite the first and last elements
        for pn in range(num_pipes):
            HN[pn].fill(0.0)
            VN[pn].fill(0.0)

        # ============ per-pipe computation ============
        for pipe in pipes:
            pn = pipe.id - 1

            l1 = links1[pn]; l2 = links2[pn]
            u0 = utype[pn][0]; d0 = dtype[pn][0]

            # ---- inner pipe ----
            if l1 and l2 and l1 != ['End'] and l2 != ['End']:
                pump = [[], []]; valve = [0, 0]
                if u0 == 'Pump':
                    link = tm.links[utype[pn][1]]
                    pump[0] = [link.curve_coef, "d"]
                    if pipe.start_node.name == link.start_node.name:
                        pump[0][1] = "s"
                    if link.operating:
                        pump[0][0] = calc_parabola_vertex(_pump_points(link, ts))
                elif u0 == 'Valve':
                    valve[0] = _valve_coef(tm.links[utype[pn][1]], ts)

                if d0 == 'Pump':
                    link = tm.links[dtype[pn][1]]
                    pump[1] = [link.curve_coef, "d"]
                    if pipe.end_node.name == link.start_node.name:
                        pump[1][1] = "s"
                    if link.operating:
                        pump[1][0] = calc_parabola_vertex(_pump_points(link, ts))
                elif d0 == 'Valve':
                    valve[1] = _valve_coef(tm.links[dtype[pn][1]], ts)

                H_u = _gather(H,    topo1[pn]);         V_u = _gather(V,    topo1[pn])
                H_d = _gather(H,    topo2[pn]);         V_d = _gather(V,    topo2[pn])
                dVdt_u = _gather(dVdt, topo1[pn]);      dVdx_u = _gather(dVdx, topo1[pn], use_b=True)
                dVdt_d = _gather(dVdt, topo2[pn]);      dVdx_d = _gather(dVdx, topo2[pn], use_b=True)

                HN[pn], VN[pn] = inner_pipe(
                    pipe, pn, dt,
                    l1, l2, utype[pn], dtype[pn], pipes,
                    H[pn], V[pn], HN[pn], VN[pn],
                    H_u, V_u, H_d, V_d,
                    pump, valve, friction, dVdt[pn], dVdx[pn],
                    dVdt_u, dVdx_u, dVdt_d, dVdx_d,
                )
                _record(pipe, ts, HN[pn], VN[pn],
                        record_velocity, record_flowrate, record_demand)

            # ---- left boundary ----
            elif (not l1) or l1 == ['End']:
                pump = [[], []]; valve = [0, 0]
                if u0 == 'Reservoir' or u0 == 'Tank':
                    HN[pn][0] = pipe.initial_head[0]
                elif u0 == 'Junction':
                    VN[pn][0] = pipe.initial_velocity[0]
                elif u0 == 'Valve':
                    link = tm.links[utype[pn][1]]
                    if link.operating:
                        VN[pn][0] = pipe.initial_velocity[0] * link.operation_rule[ts]
                    else:
                        if link.initial_status.name == 'Open':
                            VN[pn][0] = pipe.initial_velocity[0]
                        elif link.initial_status.name == 'Closed':
                            valve[0] = 0
                elif u0 == 'Pump':
                    link = tm.links[utype[pn][1]]
                    pump[0] = [link.start_node.initial_head, link.curve_coef]
                    if link.operating:
                        pump[0][1] = calc_parabola_vertex(_pump_points(link, ts))
                else:
                    warnings.warn('Pipe %s miss %s upstream.' % (pipe, u0), UserWarning)

                if d0 == 'Pump':
                    link = tm.links[dtype[pn][1]]
                    pump[1] = [link.curve_coef, "d"]
                    if pipe.end_node.name == link.start_node.name:
                        pump[1][1] = "s"
                    if link.operating:
                        pump[1][0] = calc_parabola_vertex(_pump_points(link, ts))
                elif d0 == 'Valve':
                    link = tm.links[dtype[pn][1]]
                    if link.operating:
                        valve[1] = valve_curve(link.operation_rule * 100.0, link.valve_coeff)
                    else:
                        if link.initial_status.name == 'Open':
                            valve[1] = valve_curve(100.0, link.valve_coeff)
                        elif link.initial_status.name == 'Closed':
                            valve[1] = valve_curve(0.0, link.valve_coeff)
                    if l2 == ['End']:
                        links2[pn] = []
                        l2 = []
                elif d0 == 'Junction':
                    VN[pn][-1] = pipe.initial_velocity[-1]

                H_d = _gather(H, topo2[pn]);      V_d = _gather(V, topo2[pn])
                dVdt_d = _gather(dVdt, topo2[pn]); dVdx_d = _gather(dVdx, topo2[pn], use_b=True)

                HN[pn], VN[pn] = left_boundary(
                    pipe, pn, HN[pn], VN[pn], H[pn], V[pn],
                    l2, pipes, pump, valve, dt,
                    H_d, V_d, utype[pn], dtype[pn],
                    friction, dVdt[pn], dVdx[pn], dVdt_d, dVdx_d,
                )
                _record(pipe, ts, HN[pn], VN[pn],
                        record_velocity, record_flowrate, record_demand,
                        do_start=True, do_end=True)

            # ---- right boundary ----
            elif (not l2) or l2 == ['End']:
                pump = [[], []]; valve = [0, 0]
                if d0 == 'Reservoir' or d0 == 'Tank':
                    HN[pn][-1] = pipe.initial_head[-1]
                elif d0 == 'Junction':
                    VN[pn][-1] = pipe.initial_velocity[-1]
                elif d0 == 'Valve':
                    link = tm.links[dtype[pn][1]]
                    if link.operating:
                        VN[pn][-1] = pipe.initial_velocity[-1] * link.operation_rule[ts]
                    else:
                        if link.initial_status.name == 'Open':
                            VN[pn][-1] = pipe.initial_velocity[-1]
                        elif link.initial_status.name == 'Closed':
                            VN[pn][-1] = 0.0
                elif d0 == 'Pump':
                    link_u = tm.links[utype[pn][1]]
                    link_d = tm.links[dtype[pn][1]]
                    pump[1] = [link_u.end_node.initial_head, link_d.curve_coef]
                    if link_d.operating:
                        pump[1][1] = calc_parabola_vertex(_pump_points(link_d, ts))
                else:
                    warnings.warn('Pipe %s miss %s downstream.' % (pipe, d0), UserWarning)

                if u0 == 'Pump':
                    link = tm.links[utype[pn][1]]
                    pump[0] = [link.curve_coef, "d"]
                    if pipe.start_node.name == link.start_node.name:
                        pump[0][1] = "s"
                    if link.operating:
                        pump[0][0] = calc_parabola_vertex(_pump_points(link, ts))
                elif u0 == 'Valve':
                    valve[0] = _valve_coef(tm.links[utype[pn][1]], ts)

                H_u = _gather(H, topo1[pn]);       V_u = _gather(V, topo1[pn])
                dVdt_u = _gather(dVdt, topo1[pn]); dVdx_u = _gather(dVdx, topo1[pn], use_b=True)

                HN[pn], VN[pn] = right_boundary(
                    pipe, pn, H[pn], V[pn], HN[pn], VN[pn],
                    l1, pipes, pump, valve, dt,
                    H_u, V_u, utype[pn], dtype[pn],
                    friction, dVdt[pn], dVdx[pn], dVdt_u, dVdx_u,
                )
                _record(pipe, ts, HN[pn], VN[pn],
                        record_velocity, record_flowrate, record_demand,
                        do_start=True, do_end=True)

        # ---- march in time ----
        if friction == 'unsteady':
            for pipe in pipes:
                pn = pipe.id - 1
                dVdt[pn] = (VN[pn] - V[pn]) / dt
                dVdx[pn] = np.diff(V[pn]) / (pipe.length / pipe.number_of_segments)
        
        H, HN = HN, H
        V, VN = VN, V

        for _, node in tm.nodes():
            if node.transient_node_type in ('SurgeTank', 'Chamber'):
                node.tank_shape[-2] = max(node.water_level, 0.0)
                node.tank_shape[-1] = node.tank_flow
                node.water_level_timeseries[ts] = max(node.water_level, 0.0)
                node.tank_flow_timeseries[ts] = node.tank_flow

        if tn >= 100 and ts % (tn // 100) == 0:
            pass  
            # print('  transient %3d %%' % (ts * 100 // tn))

    # ---------- finalise node heads for plotting ----------
    for pipe in pipes:
        if not isinstance(pipe.start_node._head, np.ndarray):
            pipe.start_node._head = np.copy(pipe.start_node_head)
        if not isinstance(pipe.end_node._head, np.ndarray):
            pipe.end_node._head = np.copy(pipe.end_node_head)

    tm.simulation_timestamps = tt[1:]
            
    # save object to file
    if results_obj != 'no':
        filehandler = open(results_obj +'.obj','wb')
        pickle.dump(tm, filehandler)
    else:
        pass

    logger.debug("Simulation finished in %s" % (datetime.now() - starttime))
    return tm


def MOCSimulatorOld(
        tm,
        results_obj='results',
        friction='steady'):
    """ MOC Main Function

    Parameters
    ----------
    tm : tsnet.network.model.TransientModel
        Network
    results_obj: string, optional
        the name of the results file, by default 'results'
    friction: string, optional
        friction model, e.g., 'steady', 'quasi-steady', 'unsteady',
        by default 'steady'
    kernel: KernelType, optional
        computational kernel used by MOC simulator. Three kernels are
        available: 'python', 'numba', 'cython'

    Returns
    ------
    tm : tsnet.network.model.TransientModel
            Simulated network
    """
    # determine network topology
    links1, links2, utype, dtype = topology(tm)

    tt = ['x']
    tt.append(0)
    dt = tm.time_step
    tn = int(tm.simulation_period/tm.time_step)  # Total time steps
    # check whether input is legal
    if friction not in ['steady', 'unsteady', 'quasi-steady']:
        print ("Please specify a friction model from 'steady', 'unsteady', and 'quasi-steady'")

    # determine which node of the adjacent pipe should be call:
    # if the adjacent pipe is entering the junction, then -2
    # if the adjacent pipe is leaving the junction, then 1
    a = {1:-2, -1:1}
    b = {1:-1, -1:0}
    # generat a list of pipe
    p = []
    # results from last time step
    H = [0] * tm.num_pipes
    V = [0] * tm.num_pipes
    # results at current time step
    HN = [0] * tm.num_pipes
    VN = [0] * tm.num_pipes
    # results for local and convective
    #  instantaneous acceleration
    dVdt = [0] * tm.num_pipes
    dVdx = [0] * tm.num_pipes
    Hb = 10.3 # barometric head
    for _, pipe in tm.pipes():
        p.append(pipe)

    # initial condition
    for _, pipe in tm.pipes():
        pn = pipe.id-1
        H[pn] = pipe.initial_head
        V[pn] = pipe.initial_velocity
        if friction == 'unsteady':
            dVdt[pn] = np.zeros_like(V[pn])
            dVdx[pn] = np.diff(V[pn])/(pipe.length/pipe.number_of_segments)
        else:
            dVdt[pn] = np.zeros_like(V[pn])
            dVdx[pn] = np.zeros_like(V[pn][:-1])
    for _,node in tm.nodes():
        if node.pulse_status == True:
            node.base_demand_coeff = node.demand_coeff
        if node.transient_node_type == 'SurgeTank' or node.transient_node_type == 'Chamber':
            if node.transient_node_type == 'Chamber':
                m = 1.2
                Ha = node.initial_head - node.water_level + Hb # air pressure head
                Va = node.tank_shape[0]*(node.tank_height-node.water_level) # air volume
                node.air_constant = Ha * Va**m
                node.tank_shape.insert(2,node.air_constant)
            elif node.transient_node_type == 'SurgeTank':
                node.water_level = node.initial_head
                node.tank_shape.insert(1,node.water_level)
            node.water_level_timeseries = np.zeros(tn)
            node.tank_flow_timeseries = np.zeros(tn)
            node.water_level_timeseries[0] = node.water_level
    starttime = datetime.now()
    # Start Calculation
    for ts in range(1,tn):
        # check the discrepency between initial condition and the
        # first step in the transient simulation.
        if ts == 2:
            for _,pipe in tm.pipes():
                diff1 = pipe.start_node_head[1] - pipe.start_node_head[0]
                diff2 = pipe.end_node_head[1] - pipe.end_node_head[0]
                if abs(diff1)> 5e-1:
                    print('Initial condition discrepancy of pressure (%.4f m) on the %s node' %(diff1,pipe.start_node.name))
                if abs(diff2)> 5e-1:
                    print('Initial condition discrepancy of pressure (%.4f m) on the %s node'%(diff2,pipe.end_node.name))
        if ts == 3:
            timeperstep = (datetime.now() - starttime) /2.
            est = timeperstep *tn
            logger.info('Estimated simulation time %s' %est)

        t = ts*dt
        tt.append(t)
        tp = ts/tn*100
        if ts % int(tn/10) == 0 :
            logger.info('Transient simulation completed %i %%...' %tp )
        # for burst node: emitter_coeff = burst_coeff[ts]
        for _,node in tm.nodes():
            if node.burst_status == True:
                node.emitter_coeff = node.burst_coeff[ts]
            if node.pulse_status == True:
                node.demand_coeff = node.base_demand_coeff*(1.+node.pulse_coeff[ts])

        # initialize the results at this time step
        for _, pipe in tm.pipes():
            pn = pipe.id-1
            HN[pn] =  np.zeros_like(H[pn])
            VN[pn] =  np.zeros_like(V[pn])

        for _,pipe in tm.pipes():
            pn = pipe.id-1
            # Assumption:
            # when a pipe is connected with a pump or valve,
            # the connection is not branch junction.

            # inner pipes
            if links1[pn] and links2[pn] and \
                links1[pn] != ['End'] and links2[pn] != ['End']:
                # list to store information about pump and vale
                # pump[0] and valve[0] for upstream elemnets
                # pump[1] and valve[1] for downstream elements
                pump = [[],[]]; valve = [0,0]
                # upstream
                if utype[pn][0] == 'Pump':
                    # three points for pump charatersitics curve
                    pump[0] = [tm.links[utype[pn][1]].curve_coef, "d"]
                    if pipe.start_node.name == tm.links[utype[pn][1]].start_node.name:
                        pump[0][1] = "s" # suction side
                    # calculate the coordinate of the three points
                    # based on the pump speed
                    if tm.links[utype[pn][1]].operating == True:
                        points = tm.links[utype[pn][1]].get_pump_curve().points
                        po = tm.links[utype[pn][1]].operation_rule[ts]
                        points=[(i*po,j*po**2) for (i,j) in points]
                        pump[0][0] = calc_parabola_vertex(points)

                elif utype[pn][0] == 'Valve':
                    # determine valve friction coefficients based on
                    # open percentage
                    if tm.links[utype[pn][1]].operating == True:
                        valve[0] = valve_curve(tm.links[utype[pn][1]].operation_rule[ts]*100,
                        tm.links[utype[pn][1]].valve_coeff)
                    else :
                        if tm.links[utype[pn][1]].initial_status.name == 'Open':
                            valve[0] = valve_curve(100,tm.links[utype[pn][1]].valve_coeff)
                        elif tm.links[utype[pn][1]].initial_status.name == 'Closed':
                            valve[0] = valve_curve(0,tm.links[utype[pn][1]].valve_coeff)
                # downstream
                if dtype[pn][0] == 'Pump':
                    pump[1] = [tm.links[dtype[pn][1]].curve_coef,"d"]
                    if pipe.end_node.name == tm.links[dtype[pn][1]].start_node.name:
                        pump[1][1] = "s" # suction side
                    if tm.links[dtype[pn][1]].operating == True:
                        points = tm.links[dtype[pn][1]].get_pump_curve().points
                        po = tm.links[dtype[pn][1]].operation_rule[ts]
                        points=[(i*po,j*po**2) for (i,j) in points]
                        pump[1][0] = calc_parabola_vertex(points)

                elif dtype[pn][0] == 'Valve':
                    if tm.links[dtype[pn][1]].operating == True:
                        valve[1] = valve_curve(tm.links[dtype[pn][1]].operation_rule[ts]*100,
                        tm.links[dtype[pn][1]].valve_coeff)
                    else :
                        if tm.links[dtype[pn][1]].initial_status.name == 'Open':
                            valve[1] = valve_curve(100,tm.links[dtype[pn][1]].valve_coeff)
                        elif tm.links[dtype[pn][1]].initial_status.name == 'Closed':
                            valve[1] = valve_curve(0,tm.links[dtype[pn][1]].valve_coeff)

                HN[pn], VN[pn] = inner_pipe(pipe, pn, dt,
                     links1[pn], links2[pn], utype[pn], dtype[pn], p,
                     H[pn], V[pn], HN[pn], VN[pn],
                     [H[abs(i)-1][a[np.sign(i)]] for i in links1[pn]],
                     [V[abs(i)-1][a[np.sign(i)]] for i in links1[pn]],
                     [H[abs(i)-1][a[np.sign(i)]] for i in links2[pn]],
                     [V[abs(i)-1][a[np.sign(i)]] for i in links2[pn]],
                     pump, valve, friction, dVdt[pn], dVdx[pn],
                     [dVdt[abs(i)-1][a[np.sign(i)]] for i in links1[pn]],
                     [dVdx[abs(i)-1][b[np.sign(i)]] for i in links1[pn]],
                     [dVdt[abs(i)-1][a[np.sign(i)]] for i in links2[pn]],
                     [dVdx[abs(i)-1][b[np.sign(i)]] for i in links2[pn]])
                # record results
                pipe.start_node_velocity[ts] = VN[pn][0]
                pipe.end_node_velocity[ts] = VN[pn][-1]
                pipe.start_node_flowrate[ts] = VN[pn][0]*pipe.area
                pipe.end_node_flowrate[ts] = VN[pn][-1]*pipe.area
                pipe.start_node_head[ts] = HN[pn][0]
                pipe.end_node_head[ts] = HN[pn][-1]

                if pipe.start_node.transient_node_type == 'Junction':
                    if HN[pn][0] - pipe.start_node.elevation >0:
                        h = HN[pn][0] - pipe.start_node.elevation
                        pipe.start_node.demand_discharge[ts] = pipe.start_node.demand_coeff * np.sqrt(h)
                        pipe.start_node.emitter_discharge[ts] = pipe.start_node.emitter_coeff * np.sqrt(h)
                    else: # assume reverse flow preventer installed
                        pipe.start_node.emitter_discharge[ts] = 0.
                        pipe.start_node.demand_discharge[ts] = 0.
                        warnings.warn("Negative pressure on node %s. Backflow stopped by reverse flow preventer." %pipe.start_node.name, UserWarning)

                if pipe.end_node.transient_node_type == 'Junction':
                    if HN[pn][-1]  -pipe.end_node.elevation >0:
                        h = HN[pn][-1] -pipe.end_node.elevation
                        pipe.end_node.emitter_discharge[ts] = pipe.end_node.emitter_coeff * np.sqrt(h)
                        pipe.end_node.demand_discharge[ts] = pipe.end_node.demand_coeff * np.sqrt(h)
                    else: # assume reverse flow preventer installed
                        pipe.end_node.emitter_discharge[ts] = 0.
                        pipe.end_node.demand_discharge[ts] = 0.
                        warnings.warn("Negative pressure on node %s Backflow stopped by reverse flow preventer." %pipe.start_node.name, UserWarning)

            # left boundary pipe
            elif not links1[pn] or links1[pn] == ['End']:
                pump = [[],[]]; valve = [0,0]
                # LEFT BOUNDARY
                if utype[pn][0] == 'Reservoir' or utype[pn][0] == 'Tank':
                    # head B.C.
                    HN[pn][0] = pipe.initial_head[0]
                elif utype[pn][0] == 'Junction':
                    VN[pn][0] = pipe.initial_velocity[0]
                elif utype[pn][0] == 'Valve':
                    if tm.links[utype[pn][1]].operating == True:
                        # velocity B.C.
                        VN[pn][0] = pipe.initial_velocity[0] * \
                            tm.links[utype[pn][1]].operation_rule[ts]
                    else :
                        if tm.links[utype[pn][1]].initial_status.name == 'Open':
                            VN[pn][0]  = pipe.initial_velocity[0]
                        elif tm.links[utype[pn][1]].initial_status.name == 'Closed':
                            valve[0] = 0
                elif utype[pn][0] == 'Pump':
                    # source pump
                    # pump[0][0]: elevation of the reservoir/tank
                    # pump[0][1]: three points for pump characteristic curve
                    pump[0] = [[tm.links[utype[pn][1]].start_node.initial_head][0],
                         tm.links[utype[pn][1]].curve_coef]
                    if tm.links[utype[pn][1]].operating == True:
                        points = tm.links[utype[pn][1]].get_pump_curve().points
                        po = tm.links[utype[pn][1]].operation_rule[ts]
                        points= [(i*po,j*po**2) for (i,j) in points]
                        pump[0][1] = calc_parabola_vertex(points)
                else:
                     warnings.warn ('Pipe %s miss %s upstream.' %(pipe, utype[pn][0]), UserWarning)

                # RIGHT BOUNDARY
                if dtype[pn][0] == 'Pump':
                    pump[1] = [tm.links[dtype[pn][1]].curve_coef,"d"]
                    if pipe.end_node.name == tm.links[dtype[pn][1]].start_node.name:
                        pump[1][1] = "s" # suction side
                    if tm.links[dtype[pn][1]].operating == True:
                        points = tm.links[dtype[pn][1]].get_pump_curve().points
                        po = tm.links[dtype[pn][1]].operation_rule[ts]
                        points=[(i*po,j*po**2) for (i,j) in points]
                        pump[1][0] = calc_parabola_vertex(points)

                elif dtype[pn][0] == 'Valve':
                    if tm.links[dtype[pn][1]].operating == True:
                        valve[1] = valve_curve(tm.links[dtype[pn][1]].operation_rule*100,
                        tm.links[dtype[pn][1]].valve_coeff)
                    else :
                        if tm.links[dtype[pn][1]].initial_status.name == 'Open':
                            valve[1] = valve_curve(100, tm.links[dtype[pn][1]].valve_coeff)
                        elif tm.links[dtype[pn][1]].initial_status.name == 'Closed':
                            valve[1] = valve_curve(0, tm.links[dtype[pn][1]].valve_coeff)
                    # if also the right valve end
                    if links2[pn] == ['End']:
                        links2[pn] = []

                elif dtype[pn][0] == 'Junction':
                    VN[pn][-1] = pipe.initial_velocity[-1]

                HN[pn], VN[pn] = left_boundary(pipe, pn,
                      HN[pn], VN[pn], H[pn], V[pn],
                     links2[pn], p, pump, valve, dt,
                     [H[abs(i)-1][a[np.sign(i)]] for i in links2[pn]],
                     [V[abs(i)-1][a[np.sign(i)]] for i in links2[pn]],
                     utype[pn], dtype[pn],
                     friction, dVdt[pn], dVdx[pn],
                     [dVdt[abs(i)-1][a[np.sign(i)]] for i in links2[pn]],
                     [dVdx[abs(i)-1][b[np.sign(i)]] for i in links2[pn]],)
                # record results
                pipe.start_node_velocity[ts] = VN[pn][0]
                pipe.end_node_velocity[ts] = VN[pn][-1]
                pipe.start_node_head[ts] = HN[pn][0]
                pipe.end_node_head[ts] = HN[pn][-1]
                pipe.start_node_flowrate[ts] = VN[pn][0]*pipe.area
                pipe.end_node_flowrate[ts] = VN[pn][-1]*pipe.area

                try:
                    if HN[pn][0]- pipe.start_node.elevation >0:
                        h = HN[pn][0]- pipe.start_node.elevation
                        pipe.start_node.demand_discharge[ts] = pipe.start_node.demand_coeff * np.sqrt(h)
                        pipe.start_node.emitter_discharge[ts] = pipe.start_node.emitter_coeff * np.sqrt(h)
                    else: # assume reverse flow preventer installed
                        pipe.start_node.emitter_discharge[ts] = 0.
                        pipe.start_node.demand_discharge[ts] = 0.
                        warnings.warn("Negative pressure on node %s.\
                        Backflow stopped by reverse flow preventer." %pipe.start_node.name, UserWarning)
                except:
                    pass

                try:
                    if HN[pn][-1]-pipe.end_node.elevation >0:
                        h = HN[pn][-1]-pipe.end_node.elevation
                        pipe.end_node.emitter_discharge[ts] = pipe.end_node.emitter_coeff * np.sqrt(h)
                        pipe.end_node.demand_discharge[ts] = pipe.end_node.demand_coeff * np.sqrt(h)
                    else: # assume reverse flow preventer installed
                        pipe.end_node.emitter_discharge[ts] = 0.
                        pipe.end_node.demand_discharge[ts] = 0.
                        warnings.warn("Negative pressure on node %s.\
                            Backflow stopped by reverse flow preventer." %pipe.start_node.name, UserWarning)
                except:
                    pass

            #  right boundary pipe
            elif not links2[pn] or links2[pn] == ['End']:
                pump = [[],[]]; valve = [0,0]
                # RIGHT boundary
                if dtype[pn][0] == 'Reservoir' or dtype[pn][0] == 'Tank':
                    HN[pn][-1]   =  pipe.initial_head[-1] # head of reservoir
                elif dtype[pn][0] == 'Junction':
                    VN[pn][-1] = pipe.initial_velocity[-1]
                elif dtype[pn][0] == 'Valve':
                    if tm.links[dtype[pn][1]].operating == True:
                        # valve velocity condition
                        VN[pn][-1] = pipe.initial_velocity[-1]* \
                        tm.links[dtype[pn][1]].operation_rule[ts]
                    else :
                        if tm.links[dtype[pn][1]].initial_status.name == 'Open':
                            VN[pn][-1] = pipe.initial_velocity[-1]
                        elif tm.links[dtype[pn][1]].initial_status.name == 'Closed':
                            VN[pn][-1] = 0
                # source pump
                elif dtype[pn][0] == 'Pump':
                    # pump[1][0]: elevation of the reservoir/tank
                    # pump[1][1]: three points for pump characteristic curve
                    pump[1] = [[tm.links[utype[pn][1]].end_node.initial_head][0],
                         tm.links[dtype[pn][1]].curve_coef]
                    if tm.links[dtype[pn][1]].operating == True:
                        points = tm.links[dtype[pn][1]].get_pump_curve().points
                        po = tm.links[dtype[pn][1]].operation_rule[ts]
                        points=[(i*po,j*po**2) for (i,j) in points]
                        pump[1][1] = calc_parabola_vertex(points)
                else :
                     warnings.warn('Pipe %s miss %s downstream.' %(pipe, dtype[pn][0]), UserWarning)
                # LEFT boundary
                if utype[pn][0] == 'Pump':
                    pump[0] = [tm.links[utype[pn][1]].curve_coef,"d"]
                    if pipe.start_node.name == tm.links[utype[pn][1]].start_node.name:
                        pump[0][1] = "s" # suction side
                    if tm.links[utype[pn][1]].operating == True:
                        points = tm.links[utype[pn][1]].get_pump_curve().points
                        po = tm.links[utype[pn][1]].operation_rule[ts]
                        points=[(i*po,j*po**2) for (i,j) in points]
                        pump[0][0] = calc_parabola_vertex(points)

                elif utype[pn][0] == 'Valve':
                    if tm.links[utype[pn][1]].operating == True:
                        valve[0] = valve_curve(tm.links[utype[pn][1]].operation_rule[ts]*100,
                        tm.links[utype[pn][1]].valve_coeff)
                    else :
                        if tm.links[utype[pn][1]].initial_status.name == 'Open':
                            valve[0] = valve_curve(100,tm.links[utype[pn][1]].valve_coeff)
                        elif tm.links[utype[pn][1]].initial_status.name == 'Closed':
                            valve[0] = valve_curve(0,tm.links[utype[pn][1]].valve_coeff)


                HN[pn], VN[pn] = right_boundary(pipe, pn,
                     H[pn], V[pn], HN[pn], VN[pn],
                     links1[pn], p, pump, valve,  dt,
                     [H[abs(i)-1][a[np.sign(i)]] for i in links1[pn]],
                     [V[abs(i)-1][a[np.sign(i)]] for i in links1[pn]],
                     utype[pn], dtype[pn],
                     friction, dVdt[pn], dVdx[pn],
                     [dVdt[abs(i)-1][a[np.sign(i)]] for i in links1[pn]],
                     [dVdx[abs(i)-1][b[np.sign(i)]] for i in links1[pn]],)
                # record results
                pipe.start_node_velocity[ts] = VN[pn][0]
                pipe.end_node_velocity[ts] = VN[pn][-1]
                pipe.start_node_head[ts] = HN[pn][0]
                pipe.end_node_head[ts] = HN[pn][-1]
                pipe.start_node_flowrate[ts] = VN[pn][0]*pipe.area
                pipe.end_node_flowrate[ts] = VN[pn][-1]*pipe.area

                try:
                    if HN[pn][0]- pipe.start_node.elevation >0:
                        h = HN[pn][0]- pipe.start_node.elevation
                        pipe.start_node.demand_discharge[ts] = pipe.start_node.demand_coeff * np.sqrt(h)
                        pipe.start_node.emitter_discharge[ts] = pipe.start_node.emitter_coeff * np.sqrt(h)
                    else: # assume reverse flow preventer installed
                        pipe.start_node.emitter_discharge[ts] = 0.
                        pipe.start_node.demand_discharge[ts] = 0.
                        warnings.warn("Negative pressure on node %s.\
                        Backflow stopped by reverse flow preventer." %pipe.start_node.name, UserWarning)
                except:
                    pass

                try:
                    if HN[pn][-1]-pipe.end_node.elevation >0:
                        h = HN[pn][-1]-pipe.end_node.elevation
                        pipe.end_node.emitter_discharge[ts] = pipe.end_node.emitter_coeff * np.sqrt(h)
                        pipe.end_node.demand_discharge[ts] = pipe.end_node.demand_coeff * np.sqrt(h)
                    else: # assume reverse flow preventer installed
                        pipe.end_node.emitter_discharge[ts] = 0.
                        pipe.end_node.demand_discharge[ts] = 0.
                        warnings.warn("Negative pressure on node %s.\
                            Backflow stopped by reverse flow preventer." %pipe.start_node.name, UserWarning)
                except:
                    pass

        # march in time
        for _, pipe in tm.pipes():
            pn = pipe.id-1
            # calculate instantaneous local acceleration
            # only for unsteady friction factor
            if friction == 'unsteady':
                dVdt[pn] = (VN[pn] - V[pn] )/dt
                dVdx[pn] =  np.diff(V[pn])/(pipe.length/pipe.number_of_segments)
            H[pn] = HN[pn]
            V[pn] = VN[pn]

        for _,node in tm.nodes():
            if node.transient_node_type == 'SurgeTank' or node.transient_node_type == 'Chamber':
                node.tank_shape[-2] = max(node.water_level,0)
                node.tank_shape[-1] = node.tank_flow
                node.water_level_timeseries[ts] = max(node.water_level,0)
                node.tank_flow_timeseries[ts] = node.tank_flow

    for _, pipe in tm.pipes():
        if not isinstance(pipe.start_node._head, np.ndarray):
            pipe.start_node._head = np.copy(pipe.start_node_head)
        if not isinstance(pipe.end_node._head, np.ndarray):
            pipe.end_node._head = np.copy(pipe.end_node_head)

    tm.simulation_timestamps = tt[1:]

    # save object to file
    if results_obj != 'no':
        filehandler = open(results_obj +'.obj','wb')
        pickle.dump(tm, filehandler)
    else:
        pass

    return tm

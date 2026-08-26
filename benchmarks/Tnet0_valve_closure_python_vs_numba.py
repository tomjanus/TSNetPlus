""" """
from typing import Literal, TypeAlias
import logging
from pathlib import Path
from rich import print as rprint
import matplotlib.pyplot as plt
import tsnetplus
from tsnetplus.backends import ComputeBackend
from tsnetplus.utils import Timer
from tsnetplus.benchmarking_utils import compare_results

TransientModel: TypeAlias = tsnetplus.network.TransientModel

tsnetplus.configure_logging()
logger = logging.getLogger("tsnetplus")

# Get the absolute path of the current script file
current_file_path = Path(__file__).parent.resolve()
inp_file = current_file_path / 'networks/Tnet0.inp'

def plot_backend_comparison(
    python_model: TransientModel,
    numba_model: TransientModel,
    *,
    node_id: str,
    link_id: str,
) -> None:
    """Plot selected Python and Numba results side by side."""

    time_python = python_model.simulation_timestamps
    time_numba = numba_model.simulation_timestamps

    python_node = python_model.get_node(node_id)
    numba_node = numba_model.get_node(node_id)

    python_link = python_model.get_link(link_id)
    numba_link = numba_model.get_link(link_id)

    fig, axes = plt.subplots(
        2,
        2,
        figsize=(12, 7),
        sharex='col',
    )

    # Pressure head
    axes[0, 0].plot(time_python, python_node.head)
    axes[0, 0].set_title(f"Python — Node {node_id}")
    axes[0, 0].set_ylabel("Pressure head [m]")
    axes[0, 0].grid(True)

    axes[0, 1].plot(time_numba, numba_node.head)
    axes[0, 1].set_title(f"Numba — Node {node_id}")
    axes[0, 1].set_ylabel("Pressure head [m]")
    axes[0, 1].grid(True)

    # Velocity
    axes[1, 0].plot(
        time_python,
        python_link.start_node_velocity,
    )
    axes[1, 0].set_title(f"Python — Pipe {link_id}")
    axes[1, 0].set_xlabel("Time [s]")
    axes[1, 0].set_ylabel("Velocity [m/s]")
    axes[1, 0].grid(True)

    axes[1, 1].plot(
        time_numba,
        numba_link.start_node_velocity,
    )
    axes[1, 1].set_title(f"Numba — Pipe {link_id}")
    axes[1, 1].set_xlabel("Time [s]")
    axes[1, 1].set_ylabel("Velocity [m/s]")
    axes[1, 1].grid(True)

    fig.suptitle("Python vs Numba backend comparison")
    fig.tight_layout()
    plt.show()


# Open an example network and create a transient model
def instantiate_model_from_file(inp_file: Path) -> TransientModel:
    """ """
    tm = tsnetplus.network.TransientModel(inp_file)
    return tm


def setup_and_run_transient_model(
        tm,
        friction_type: Literal['steady', 'quasi-steady', 'unsteady'],
        kernel: ComputeBackend) -> TransientModel:
    """ """
    # Set wavespeed
    tm.set_wavespeed(1200.) # m/s
    # Set time options
    dt = 0.01
    tf = 120   # simulation time [s]
    tm.set_time(tf,dt)
    # Set valve closure
    tc = 0.4 # valve closure period [s]
    ts = 0 # valve closure start time [s]
    se = 0 # end open percentage [s]
    m = 1 # closure constant [dimensionless]
    valve_op = [tc, ts, se, m]
    tm.valve_closure('3',valve_op)
    # Initialize steady state simulation
    t0 = 0. # initialize the simulation at 0 [s]
    engine = 'PDD' # demand driven simulator
    tm = tsnetplus.simulation.initialize(tm, t0, engine, kernel)
    # Transient simulation
    results_obj = 'no' # name of the object for saving simulation results
    tm = tsnetplus.simulation.MOCSimulator(tm, results_obj, friction_type, kernel)
    return tm


if __name__ == "__main__":
    friction_type = 'steady'
    # Instantiate model from inp_file
    transient_model_python = instantiate_model_from_file(inp_file)
    kernel = ComputeBackend.PYTHON
    rprint(f"\nRunning [blue bold]Tnet0.inp[/blue bold] with the [red bold]Python[/red bold] backend and {friction_type} friction.\n")
    timer = Timer()
    timer.start()
    transient_model_python = setup_and_run_transient_model(
        tm=transient_model_python,
        friction_type = friction_type,
        kernel=kernel
    )
    timer.stop()
    # Re-Instantiate model from inp_file
    transient_model_numba = instantiate_model_from_file(inp_file)
    kernel = ComputeBackend.NUMBA
    rprint(f"\nRunning [blue bold]Tnet0.inp[/blue bold] with the [red bold]Numba[/red bold] backend and {friction_type} friction.\n")
    timer = Timer()
    timer.start()
    transient_model_numba = setup_and_run_transient_model(
        tm=transient_model_numba,
        friction_type = friction_type,
        kernel=kernel
    )
    timer.stop()
    
    try:
        compare_results(
            transient_model_python,
            transient_model_numba,
            rtol = 1e-5,
            atol = 1e-6
        )
    except AssertionError:
        logger.exception(
            "[bold red]Python and Numba results are not numerically equivalent.[/bold red]"
        )
        
    plot_backend_comparison(transient_model_python, transient_model_numba, node_id = '2', link_id = '1')

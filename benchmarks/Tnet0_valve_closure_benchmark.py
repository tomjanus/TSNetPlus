from pathlib import Path
from typing import Literal
import cProfile
import pstats
import tsnetplus

# Get the absolute path of the current script file
current_file_path = Path(__file__).parent.resolve()
inp_file = current_file_path / 'networks/Tnet0.inp'


# Open an example network and create a transient model
def instantiate_model_from_file(inp_file: Path):
    """ """
    tm = tsnetplus.network.TransientModel(inp_file)
    return tm
    
def setup_transient_model(tm, friction_type: Literal['steady', 'quasi-steady', 'unsteady']):
    """ """
    # Set wavespeed
    tm.set_wavespeed(1200.) # m/s
    # Set time options
    dt = 0.01
    tf = 25   # simulation period [s]
    tm.set_time(tf,dt)
    # Set valve closure
    tc = 0 # valve closure period [s]
    ts = 0 # valve closure start time [s]
    se = 0 # end open percentage [s]
    m = 1 # closure constant [dimensionless]
    valve_op = [tc, ts, se, m]
    tm.valve_closure('3',valve_op)
    # Initialize steady state simulation
    t0 = 0. # initialize the simulation at 0 [s]
    engine = 'PDD' # demand driven simulator
    tm = tsnetplus.simulation.initialize(tm, t0, engine)
    # Transient simulation
    results_obj = 'no' # name of the object for saving simulation results
    tm = tsnetplus.simulation.MOCSimulator(tm, results_obj, friction_type)

if __name__ == "__main__":
    friction_type = 'quasi-steady'
    profiler = cProfile.Profile()
    profiler.enable()
    # Run the analysis
    transient_model = instantiate_model_from_file(inp_file)
    setup_transient_model(tm=transient_model, friction_type = friction_type)
    profiler.disable()
    stats = pstats.Stats(profiler)
    stats.strip_dirs()
    stats.sort_stats("cumtime")
    stats.print_stats(40)

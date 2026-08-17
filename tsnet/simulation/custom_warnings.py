""" """
class SimulationWarning(UserWarning):
    """Warning raised during transient-model simulation."""


class InitializationWarning(UserWarning):
    """Warning raised during transient-model initialization."""


class ExcessiveFrictionWarning(InitializationWarning):
    """Warning for unusually large Darcy-Weisbach coefficients."""


class SuspiciousOutputsWarning(SimulationWarning):
    """Warning for unusually large Darcy-Weisbach coefficients."""


class NegativePressureWarning(SimulationWarning):
    """Warning for negative pressure in the simulation."""
""" """

class InitializationError(RuntimeError):
    """Base exception for transient-model initialization errors."""


class InvalidEngineError(InitializationError, ValueError):
    """Raised when an unsupported steady-state engine is requested."""


class InitialConditionError(InitializationError):
    """Raised when initial hydraulic conditions cannot be obtained."""


class InitialConditionTimeError(InitialConditionError):
    """Raised when the requested initial-condition time is unavailable."""


class PumpCurveError(InitializationError):
    """Base exception for invalid pump-curve definitions."""


class UnsupportedPumpCurveError(PumpCurveError):
    """Raised when a pump curve has an unsupported number of points."""


class InvalidInitialConditionError(InitializationError):
    """Raised when calculated initial hydraulic conditions are invalid."""


class InvalidFrictionModelError(ValueError):
    """Raised when an unsupported friction model is requested."""


class ResultNotFoundError(KeyError):
    """Raised when the value for a variable cannot be found."""
    
    
class ResultNonFiniteError(ValueError):
    """Raised when the result is +-inf or NaN"""
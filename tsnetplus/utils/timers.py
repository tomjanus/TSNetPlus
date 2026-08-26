""" """
from typing import Callable, Any
import functools
import time
from rich import print as rprint


def timer(func: Callable[..., Any]) -> Callable[..., Any]:
    """
    Decorator that times the execution of any function or method and prints the result.
    
    Args:
        func: The function to be timed
        
    Returns:
        Wrapped function that prints execution time
        
    Example:
        @timer
        def my_method(self):
            # some code
            pass
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs) -> Any:
        start_time = time.perf_counter()
        result = func(*args, **kwargs)
        end_time = time.perf_counter()
        execution_time = end_time - start_time
        
        # Get function name and class name if it's a method
        func_name = func.__name__
        if args and hasattr(args[0], '__class__'):
            class_name = args[0].__class__.__name__
            rprint(f"⏱️  {class_name}.{func_name}() executed in {execution_time:.6f} seconds")
        else:
            rprint(f"⏱️  {func_name}() executed in {execution_time:.6f} seconds")
        
        return result
    return wrapper
    
    
class Timer:
    """Measure elapsed wall-clock time using a high-resolution timer.

    The timer is controlled explicitly using :meth:`start` and :meth:`stop`,
    allowing multiple statements or blocks of code to be timed without
    requiring them to be placed inside a function.

    Examples
    --------
    >>> timer = Timer()
    >>> timer.start()
    >>> do_something()
    >>> do_something_else()
    >>> elapsed = timer.stop()

    Notes
    -----
    ``time.perf_counter()`` is used because it is intended for measuring
    short-duration intervals and provides high-resolution monotonic timing.
    """
    def __init__(self, name: str | None = None) -> None:
        self.name = name
        self._start_time: float | None = None

    @property
    def is_running(self) -> bool:
        """Return whether the timer is currently running."""
        return self._start_time is not None

    def start(self, *, print_start: bool = True) -> None:
        """Start the timer.
        
        Parameters
        ----------
        print_start : bool, default=True
            Whether to print the start info.

        Raises
        ------
        RuntimeError
            If the timer is already running.
        """
        if self.is_running:
            raise RuntimeError("Timer is already running.")
        if print_start:
            label = f"{self.name}: " if self.name else ""
            rprint(f"⏱️ {label} Timer starting at: {time.strftime("%I:%M:%S %p")}")
        self._start_time = time.perf_counter()

    def stop(self, *, print_result: bool = True) -> float:
        """Stop the timer and return the elapsed time in seconds.

        Parameters
        ----------
        print_result : bool, default=True
            Whether to print the elapsed time.
            
        Returns
        -------
        float
            Elapsed wall-clock time in seconds.

        Raises
        ------
        RuntimeError
            If the timer is not running.
        """
        if self._start_time is None:
            raise RuntimeError("Timer is not running.")
        elapsed = time.perf_counter() - self._start_time
        self._start_time = None
        if print_result:
            label = f"{self.name}: " if self.name else ""
            rprint(f"⏱️ {label} Elapsed time: {elapsed:.6f} seconds")
        return elapsed

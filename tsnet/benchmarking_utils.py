""" """
import logging
import numpy as np
import tsnet

logger = logging.getLogger("tsnet")

_MISSING = object()

def _compare_result(
    python_obj,
    numba_obj,
    attribute: str,
    *,
    name: str,
    rtol: float,
    atol: float,
) -> bool:
    """Compare one result attribute between Python and Numba objects.

    Returns
    -------
    bool
        ``True`` if a result was compared, ``False`` if the attribute
        was absent from both objects.
    """
    python_result = getattr(python_obj, attribute, _MISSING)
    numba_result = getattr(numba_obj, attribute, _MISSING)
    # Attribute is not available for either backend.
    if python_result is _MISSING and numba_result is _MISSING:
        return False
    # Attribute exists for only one backend.
    if python_result is _MISSING or numba_result is _MISSING:
        python_status = "missing" if python_result is _MISSING else "present"
        numba_status = "missing" if numba_result is _MISSING else "present"

        raise AssertionError(
            f"Result attribute mismatch for {name}: "
            f"Python={python_status}, Numba={numba_status}."
        )
    # Attribute exists on both objects, but both results are None.
    if python_result is None and numba_result is None:
        return False
    # One backend returned None while the other returned a result.
    if python_result is None or numba_result is None:
        raise AssertionError(
            f"Result mismatch for {name}: "
            f"Python={python_result!r}, "
            f"Numba={numba_result!r}"
        )
    # Both results exist: compare shapes first.
    np.testing.assert_equal(
        np.shape(python_result),
        np.shape(numba_result),
        err_msg=f"Shape mismatch for {name}",
    )
    # Then compare numerical values.
    np.testing.assert_allclose(
        python_result,
        numba_result,
        rtol=rtol,
        atol=atol,
        err_msg=f"Numerical mismatch for {name}",
    )
    return True

def compare_results(
    python_model: tsnet.network.TransientModel,
    numba_model: tsnet.network.TransientModel,
    *,
    rtol: float = 1e-8,
    atol: float = 1e-12,
) -> None:
    """Verify that Python and Numba simulation results are equivalent.

    Parameters
    ----------
    python_model
        Transient model simulated using the Python backend.
    numba_model
        Transient model simulated using the Numba backend.
    rtol
        Relative tolerance used for numerical comparison.
    atol
        Absolute tolerance used for numerical comparison.

    Raises
    ------
    AssertionError
        If the simulation timestamps, network structure, result shapes,
        or numerical results differ beyond the specified tolerances.
    """
    logger.info(
        "Comparing Python and Numba simulation results "
        "(rtol=%g, atol=%g).",
        rtol,
        atol,
    )
    # ------------------------------------------------------------------
    # Time axis
    # ------------------------------------------------------------------
    np.testing.assert_equal(
        python_model.simulation_timestamps,
        numba_model.simulation_timestamps,
        err_msg="Simulation timestamps differ between Python and Numba.",
    )
    logger.info("Simulation timestamps: [green]OK[/green]")

    # ------------------------------------------------------------------
    # Nodes
    # ------------------------------------------------------------------
    python_nodes = set(python_model.nodes)
    numba_nodes = set(numba_model.nodes)
    if python_nodes != numba_nodes:
        raise AssertionError(
            "Node sets differ: "
            f"only in Python={python_nodes - numba_nodes}, "
            f"only in Numba={numba_nodes - python_nodes}"
        )
    node_attributes = (
        "head",
        "emitter_discharge",
        "demand_discharge",
    )
    node_comparisons = 0
    node_skipped = 0

    for node_id in python_model.nodes:
        python_node = python_model.get_node(node_id)
        numba_node = numba_model.get_node(node_id)

        for attribute in node_attributes:
            compared = _compare_result(
                python_node,
                numba_node,
                attribute,
                name=f"node {node_id!r}, attribute {attribute!r}",
                rtol=rtol,
                atol=atol,
            )

            if compared:
                node_comparisons += 1
            else:
                node_skipped += 1

    logger.info(
        "Node results: [green]OK[/green] "
        "(%d comparisons, %d skipped).",
        node_comparisons,
        node_skipped,
    )

    # ------------------------------------------------------------------
    # Links
    # ------------------------------------------------------------------
    python_links = set(python_model.links)
    numba_links = set(numba_model.links)
    if python_links != numba_links:
        raise AssertionError(
            "Link sets differ: "
            f"only in Python={python_links - numba_links}, "
            f"only in Numba={numba_links - python_links}"
        )
    link_attributes = (
        "start_node_head",
        "end_node_head",
        "start_node_velocity",
        "end_node_velocity",
        "start_node_flowrate",
        "end_node_flowrate",
    )
    link_comparisons = 0
    link_skipped = 0

    for link_id in python_model.links:
        python_link = python_model.get_link(link_id)
        numba_link = numba_model.get_link(link_id)

        for attribute in link_attributes:
            compared = _compare_result(
                python_link,
                numba_link,
                attribute,
                name=f"link {link_id!r}, attribute {attribute!r}",
                rtol=rtol,
                atol=atol,
            )
            if compared:
                link_comparisons += 1
            else:
                link_skipped += 1


    logger.info(
        "Link results: [green]OK[/green] "
        "(%d comparisons, %d skipped).",
        link_comparisons,
        link_skipped,
    )

    logger.info(
        "[bold green]Python and Numba results are "
        "numerically equivalent.[/bold green]"
    )

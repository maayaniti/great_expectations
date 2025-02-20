from __future__ import annotations

import logging
from typing import TYPE_CHECKING, List, Literal, Optional, Union

from great_expectations.expectations.expectation import (
    MulticolumnMapExpectation,
)
from great_expectations.render import RenderedStringTemplateContent
from great_expectations.render.components import LegacyRendererType
from great_expectations.render.renderer.renderer import renderer
from great_expectations.render.util import (
    num_to_str,
    substitute_none_for_missing,
)

if TYPE_CHECKING:
    from great_expectations.core import (
        ExpectationConfiguration,
        ExpectationValidationResult,
    )

logger = logging.getLogger(__name__)


class ExpectMulticolumnSumToEqual(MulticolumnMapExpectation):
    """Expect that the sum of row values in a specified column list is the same for each row, and equal to a specified sum total.

    expect_multicolumn_sum_to_equal is a \
    [Multicolumn Map Expectation](https://docs.greatexpectations.io/docs/guides/expectations/creating_custom_expectations/how_to_create_custom_multicolumn_map_expectations).

    Args:
        column_list (tuple or list): Set of columns to be checked
        sum_total (int or float): expected sum of columns

    Keyword Args:
        ignore_row_if (str): "all_values_are_missing", "any_value_is_missing", "never"

    Other Parameters:
        result_format (str or None): \
            Which output mode to use: BOOLEAN_ONLY, BASIC, COMPLETE, or SUMMARY. \
            For more detail, see [result_format](https://docs.greatexpectations.io/docs/reference/expectations/result_format).
        catch_exceptions (boolean or None): \
            If True, then catch exceptions and include them as part of the result object. \
            For more detail, see [catch_exceptions](https://docs.greatexpectations.io/docs/reference/expectations/standard_arguments/#catch_exceptions).
        meta (dict or None): \
            A JSON-serializable dictionary (nesting allowed) that will be included in the output without \
            modification. For more detail, see [meta](https://docs.greatexpectations.io/docs/reference/expectations/standard_arguments/#meta).

    Returns:
        An [ExpectationSuiteValidationResult](https://docs.greatexpectations.io/docs/terms/validation_result)

        Exact fields vary depending on the values passed to result_format, catch_exceptions, and meta.
    """

    sum_total: Union[int, float]
    ignore_row_if: Literal[
        "all_values_are_missing", "any_value_is_missing", "never"
    ] = "all_values_are_missing"

    # This dictionary contains metadata for display in the public gallery
    library_metadata = {
        "maturity": "production",
        "tags": [
            "core expectation",
            "multi-column expectation",
        ],
        "contributors": ["@great_expectations"],
        "requirements": [],
        "has_full_test_suite": True,
        "manually_reviewed_code": True,
    }

    map_metric = "multicolumn_sum.equal"
    success_keys = ("mostly", "sum_total")
    args_keys = (
        "column_list",
        "sum_total",
    )

    @classmethod
    @renderer(renderer_type=LegacyRendererType.PRESCRIPTIVE)
    @renderer(renderer_type="renderer.prescriptive")
    def _prescriptive_renderer(
        cls,
        configuration: Optional[ExpectationConfiguration] = None,
        result: Optional[ExpectationValidationResult] = None,
        runtime_configuration: Optional[dict] = None,
        **kwargs,
    ) -> List[RenderedStringTemplateContent]:
        runtime_configuration = runtime_configuration or {}
        styling = runtime_configuration.get("styling")
        params = substitute_none_for_missing(
            configuration.kwargs,
            ["column_list", "sum_total", "mostly"],
        )
        if params["mostly"] is not None:
            params["mostly_pct"] = num_to_str(
                params["mostly"] * 100, no_scientific=True
            )
        mostly_str = (
            ""
            if params.get("mostly") is None
            else ", at least $mostly_pct % of the time"
        )
        sum_total = params.get("sum_total")  # noqa: F841

        column_list_str = ""
        for idx in range(len(params["column_list"]) - 1):
            column_list_str += f"$column_list_{idx!s}, "
            params[f"column_list_{idx!s}"] = params["column_list"][idx]
        last_idx = len(params["column_list"]) - 1
        column_list_str += f"$column_list_{last_idx!s}"
        params[f"column_list_{last_idx!s}"] = params["column_list"][last_idx]
        template_str = (
            f"Sum across columns {column_list_str} must be $sum_total{mostly_str}."
        )
        return [
            RenderedStringTemplateContent(
                **{
                    "content_block_type": "string_template",
                    "string_template": {
                        "template": template_str,
                        "params": params,
                        "styling": styling,
                    },
                }
            )
        ]

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Dict, Optional, Union

from great_expectations.compatibility.typing_extensions import override
from great_expectations.core.evaluation_parameters import (
    EvaluationParameterDict,  # noqa: TCH001
)
from great_expectations.expectations.expectation import (
    ColumnAggregateExpectation,
    render_evaluation_parameter_string,
)
from great_expectations.render import (
    LegacyDescriptiveRendererType,
    LegacyRendererType,
    RenderedStringTemplateContent,
)
from great_expectations.render.renderer.renderer import renderer
from great_expectations.render.renderer_configuration import (
    RendererConfiguration,
    RendererValueType,
)
from great_expectations.render.util import (
    handle_strict_min_max,
    parse_row_condition_string_pandas_engine,
    substitute_none_for_missing,
)

if TYPE_CHECKING:
    from great_expectations.core import (
        ExpectationConfiguration,
        ExpectationValidationResult,
    )
    from great_expectations.execution_engine import ExecutionEngine
    from great_expectations.render.renderer_configuration import AddParamArgs


class ExpectColumnMeanToBeBetween(ColumnAggregateExpectation):
    """Expect the column mean to be between a minimum value and a maximum value (inclusive).

    expect_column_mean_to_be_between is a \
    [Column Aggregate Expectation](https://docs.greatexpectations.io/docs/guides/expectations/creating_custom_expectations/how_to_create_custom_column_aggregate_expectations).

    Args:
        column (str): \
            The column name.
        min_value (float or None): \
            The minimum value for the column mean.
        max_value (float or None): \
            The maximum value for the column mean.
        strict_min (boolean): \
            If True, the column mean must be strictly larger than min_value, default=False
        strict_max (boolean): \
            If True, the column mean must be strictly smaller than max_value, default=False

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

    Notes:
        * min_value and max_value are both inclusive unless strict_min or strict_max are set to True.
        * If min_value is None, then max_value is treated as an upper bound.
        * If max_value is None, then min_value is treated as a lower bound.
        * observed_value field in the result object is customized for this expectation to be a float \
            representing the true mean for the column

    See Also:
        [expect_column_median_to_be_between](https://greatexpectations.io/expectations/expect_column_median_to_be_between)
        [expect_column_stdev_to_be_between](https://greatexpectations.io/expectations/expect_column_stdev_to_be_between)
    """

    min_value: Union[int, float, EvaluationParameterDict, datetime, None] = None
    max_value: Union[int, float, EvaluationParameterDict, datetime, None] = None
    strict_min: bool = False
    strict_max: bool = False

    # This dictionary contains metadata for display in the public gallery
    library_metadata = {
        "maturity": "production",
        "tags": ["core expectation", "column aggregate expectation"],
        "contributors": ["@great_expectations"],
        "requirements": [],
        "has_full_test_suite": True,
        "manually_reviewed_code": True,
    }

    # Setting necessary computation metric dependencies and defining kwargs, as well as assigning kwargs default values\
    metric_dependencies = ("column.mean",)
    success_keys = (
        "min_value",
        "strict_min",
        "max_value",
        "strict_max",
    )

    args_keys = (
        "column",
        "min_value",
        "max_value",
        "strict_min",
        "strict_max",
    )

    kwargs_json_schema_base_properties = {
        "result_format": {
            "oneOf": [
                {"type": "null"},
                {
                    "type": "string",
                    "enum": ["BOOLEAN_ONLY", "BASIC", "SUMMARY", "COMPLETE"],
                },
                {
                    "type": "object",
                    "properties": {
                        "result_format": {
                            "type": "string",
                            "enum": ["BOOLEAN_ONLY", "BASIC", "SUMMARY", "COMPLETE"],
                        },
                        "partial_unexpected_count": {"type": "number"},
                    },
                },
            ],
            "default": "BASIC",
        },
        "catch_exceptions": {
            "oneOf": [{"type": "null"}, {"type": "boolean"}],
            "default": "false",
        },
        "meta": {"type": "object"},
    }

    kwargs_json_schema = {
        "type": "object",
        "properties": {
            **kwargs_json_schema_base_properties,
            "column": {"type": "string"},
            "min_value": {"oneOf": [{"type": "null"}, {"type": "number"}]},
            "max_value": {"oneOf": [{"type": "null"}, {"type": "number"}]},
            "strict_min": {
                "oneOf": [{"type": "null"}, {"type": "boolean"}],
                "default": "false",
            },
            "strict_max": {
                "oneOf": [{"type": "null"}, {"type": "boolean"}],
                "default": "false",
            },
        },
        "required": ["column"],
    }

    @classmethod
    @override
    def _prescriptive_template(
        cls,
        renderer_configuration: RendererConfiguration,
    ) -> RendererConfiguration:
        add_param_args: AddParamArgs = (
            ("column", RendererValueType.STRING),
            ("min_value", [RendererValueType.NUMBER, RendererValueType.DATETIME]),
            ("max_value", [RendererValueType.NUMBER, RendererValueType.DATETIME]),
            ("strict_min", RendererValueType.BOOLEAN),
            ("strict_max", RendererValueType.BOOLEAN),
        )
        for name, param_type in add_param_args:
            renderer_configuration.add_param(name=name, param_type=param_type)

        params = renderer_configuration.params

        if not params.min_value and not params.max_value:
            template_str = "mean may have any numerical value."
        else:
            at_least_str = "greater than or equal to"
            if params.strict_min:
                at_least_str = cls._get_strict_min_string(
                    renderer_configuration=renderer_configuration
                )
            at_most_str = "less than or equal to"
            if params.strict_max:
                at_most_str = cls._get_strict_max_string(
                    renderer_configuration=renderer_configuration
                )

            if params.min_value and params.max_value:
                template_str = f"mean must be {at_least_str} $min_value and {at_most_str} $max_value."
            elif not params.min_value:
                template_str = f"mean must be {at_most_str} $max_value."
            else:
                template_str = f"mean must be {at_least_str} $min_value."

        if renderer_configuration.include_column_name:
            template_str = f"$column {template_str}"

        renderer_configuration.template_str = template_str

        return renderer_configuration

    @classmethod
    @override
    @renderer(renderer_type=LegacyRendererType.PRESCRIPTIVE)
    @render_evaluation_parameter_string
    def _prescriptive_renderer(  # type: ignore[override] # TODO: Fix this type ignore
        cls,
        configuration: ExpectationConfiguration,
        result: Optional[ExpectationValidationResult] = None,
        runtime_configuration: Optional[dict] = None,
        **kwargs,
    ):
        runtime_configuration = runtime_configuration or {}
        include_column_name = (
            False if runtime_configuration.get("include_column_name") is False else True
        )
        styling = runtime_configuration.get("styling")
        params = substitute_none_for_missing(
            configuration.kwargs,
            [
                "column",
                "min_value",
                "max_value",
                "row_condition",
                "condition_parser",
                "strict_min",
                "strict_max",
            ],
        )

        template_str = ""
        if (params["min_value"] is None) and (params["max_value"] is None):
            template_str = "mean may have any numerical value."
        else:
            at_least_str, at_most_str = handle_strict_min_max(params)

            if params["min_value"] is not None and params["max_value"] is not None:
                template_str = f"mean must be {at_least_str} $min_value and {at_most_str} $max_value."
            elif params["min_value"] is None:
                template_str = f"mean must be {at_most_str} $max_value."
            elif params["max_value"] is None:
                template_str = f"mean must be {at_least_str} $min_value."

        if include_column_name:
            template_str = f"$column {template_str}"

        if params["row_condition"] is not None:
            (
                conditional_template_str,
                conditional_params,
            ) = parse_row_condition_string_pandas_engine(params["row_condition"])
            template_str = f"{conditional_template_str}, then {template_str}"
            params.update(conditional_params)

        return [
            RenderedStringTemplateContent(
                content_block_type="string_template",
                string_template={
                    "template": template_str,
                    "params": params,
                    "styling": styling,
                },
            )
        ]

    @classmethod
    @renderer(renderer_type=LegacyDescriptiveRendererType.STATS_TABLE_MEAN_ROW)
    def _descriptive_stats_table_mean_row_renderer(
        cls,
        configuration: Optional[ExpectationConfiguration] = None,
        result: Optional[ExpectationValidationResult] = None,
        runtime_configuration: Optional[dict] = None,
        **kwargs,
    ):
        assert result, "Must pass in result."
        return [
            {
                "content_block_type": "string_template",
                "string_template": {
                    "template": "Mean",
                    "tooltip": {"content": "expect_column_mean_to_be_between"},
                },
            },
            f"{result.result['observed_value']:.2f}",
        ]

    @override
    def _validate(
        self,
        configuration: ExpectationConfiguration,
        metrics: Dict,
        runtime_configuration: Optional[dict] = None,
        execution_engine: Optional[ExecutionEngine] = None,
    ):
        return self._validate_metric_value_between(
            metric_name="column.mean",
            configuration=configuration,
            metrics=metrics,
            runtime_configuration=runtime_configuration,
            execution_engine=execution_engine,
        )

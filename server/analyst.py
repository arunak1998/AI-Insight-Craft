import argparse
from typing import List, Dict, Any
from pydantic import Field
from mcp.server.fastmcp import FastMCP
from glob import glob
import polars as pl
import sys
import os

file_location = os.getenv("FILE_LOCATION", "data/*.csv")

mcp = FastMCP("analyst", host="0.0.0.0", port=8050, dependencies=["polars"])

@mcp.tool(
    name="get_files_list",
    description="Get list of source CSV files",
    structured_output={
        "type": "array",
        "items": {"type": "string"}
    }
)
def get_files_list() -> List[str]:
    return glob(file_location)

def read_file(file_location: str, file_type: str = "csv") -> pl.DataFrame:
    if file_type == "csv":
        return pl.read_csv(file_location)
    elif file_type == "parquet":
        return pl.read_parquet(file_location)
    else:
        raise ValueError(f"Unsupported file type: {file_type}")

def read_file_list(file_locations: List[str], file_type: str = "csv") -> pl.DataFrame:
    """
    Lazy read multiple files for performance
    """
    if file_type == "csv":
        dfs = [pl.scan_csv(f) for f in file_locations]  # lazy execution
        return pl.concat(dfs).collect()  # compute only once
    elif file_type == "parquet":
        dfs = pl.read_parquet(file_locations)
        return dfs
    else:
        raise ValueError(f"Unsupported file type: {file_type}")

@mcp.tool()
def get_schema(file_location: str, file_type: str = "csv") -> List[Dict[str, Any]]:
    df = read_file(file_location, file_type)
    return [{"name": col, "dtype": str(dtype)} for col, dtype in df.schema.items()]

polars_sql_aggregate_functions = [
    "avg",
    "count",
    "first",
    "last",
    "max",
    "median",
    "min",
    "sum",
    "quantile_count",
    "quantile_disc",
    "stddev",
    "sum",
    "variance",
]

polars_sql_array_functions = [
    "array_agg",
    "array_contains",
    "array_get",
    "array_length",
    "array_lower",
    "array_mean",
    "array_reverse",
    "array_sum",
    "array_to_string",
    "array_unique",
    "array_upper",
    "unnest",
]

polars_sql_bitwise_functions = [
    "bit_and",
    "bit_count",
    "bit_or",
    "bit_xor",
]

polars_sql_conditional_functions = [
    "coalesce",
    "greatest",
    "if",
    "ifnull",
    "least",
    "nullif",
]

polars_sql_mathematical_functions = [
    "abs",
    "cbrt",
    "ceil",
    "div",
    "exp",
    "floor",
    "ln",
    "log2",
    "log10",
    "mod",
    "pi",
    "pow",
    "round",
    "sign",
    "sqrt",
]

polars_sql_string_functions = [
    "bit_length",
    "concat",
    "concat_ws",
    "date",
    "ends_with",
    "initcap",
    "left",
    "length",
    "lower",
    "ltrim",
    "normalize",
    "octet_length",
    "regexp_like",
    "replace",
    "reverse",
    "right",
    "rtrim",
    "starts_with",
    "strpos",
    "strptime",
    "substr",
    "timestamp",
    "upper",
]

polars_sql_temporal_functions = [
    "date_part",
    "extract",
    "strftime",
]

polars_sql_type_functions = [
    "cast",
    "try_cast",
]

polars_sql_trigonometric_functions = [
    "acos",
    "acosd",
    "asin",
    "asind",
    "atan",
    "atand",
    "atan2",
    "atan2d",
    "cot",
    "cotd",
    "cos",
    "cosd",
    "degrees",
    "radians",
    "sin",
    "sind",
    "tan",
    "tand",
]

polars_sql_functions = {
    "aggregate": polars_sql_aggregate_functions,
    "array": polars_sql_array_functions,
    "bitwise": polars_sql_bitwise_functions,
    "conditional": polars_sql_conditional_functions,
    "mathematical": polars_sql_mathematical_functions,
    "string": polars_sql_string_functions,
    "temporal": polars_sql_temporal_functions,
    "type": polars_sql_type_functions,
    "trigonometric": polars_sql_trigonometric_functions,
}


def gen_polars_sql_functions_str():
    sql_functions_agg = []
    for sql_fn_category, sql_fns in polars_sql_functions.items():
        sql_fns_str = ["- " + sql_fn.capitalize() for sql_fn in sql_fns]
        sql_fns_str = "\n".join(sql_fns_str)
        sql_fn_with_header = f"{sql_fn_category.capitalize()}: \n{sql_fns_str}\n\n"
        sql_functions_agg.append(sql_fn_with_header)
    return "\n".join(sql_functions_agg)


query_description = f"""
The polars sql query to be executed.
polars sql query must use the table name as `self` to refer to the source data.
Supported functions are:
{gen_polars_sql_functions_str()}
"""


@mcp.tool()
def execute_polars_sql(
    file_locations: List[str],
    query: str = Field(
        description=query_description,
    ),
    file_type: str = Field(
        description="The type of the file to be read. Supported types are csv and parquet",
        default="csv",
    ),
) -> List[Dict[str, Any]]:
    """
    Reads the data from the given file locations. Note that file_locations
    can be a list of multiple files. However, all files must have the same schema
    and the same columns. Executes the given polars sql query and returns the result.
    Note that the polars sql query must use the table name as `self` to refer to the source data.
    """
    df = read_file_list(file_locations, file_type)
    op_df = df.sql(query)
    output_records = op_df.to_dicts()
    return output_records




def main():
    # prevent protocol corruption by prints

    print("[server] starting…", file=sys.stderr, flush=True)
    mcp.run(
        transport="sse",

    )


if __name__ == "__main__":
    main()

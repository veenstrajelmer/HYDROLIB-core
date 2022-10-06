"""util.py provides additional utility methods related to handling ini files.
"""
from enum import Enum
from operator import eq
from typing import Any, Callable, Dict, List, Optional, Type

from pydantic.class_validators import root_validator, validator
from pydantic.fields import ModelField
from pydantic.main import BaseModel
from hydrolib.core.io.common.models import LocationType

from hydrolib.core.utils import operator_str, str_is_empty_or_none, to_list


def get_split_string_on_delimiter_validator(*field_name: str):
    """Get a validator to split strings passed to the specified field_name.

    Strings are split based on an automatically selected provided delimiter.
    The delimiter is the field's own delimiter, if that was defined using
    Field(.., delimiter=".."). Otherwise, the delimiter is the field's parent
    class's delimiter (which should be (subclass of) INIBasedModel.)
    The validator splits a string value into a list of substrings before any
    other validation takes place.

    Returns:
        the validator which splits strings on the provided delimiter.
    """

    def split(cls, v: Any, field: ModelField):
        if isinstance(v, str):
            v = v.split(cls.get_list_field_delimiter(field.name))
            v = [item.strip() for item in v if item != ""]
        return v

    return validator(*field_name, allow_reuse=True, pre=True)(split)


def get_enum_validator(*field_name: str, enum: Type[Enum]):
    """
    Get a case-insensitive enum validator that will returns the corresponding enum value.
    If the input is a list, then each list value is checked individually.

    Args:
        enum (Type[Enum]): The enum type for which to validate.
    """

    def get_enum(v):
        for entry in enum:
            if entry.lower() == v.lower():
                return entry
        return v

    return validator(*field_name, allow_reuse=True, pre=True, each_item=True)(get_enum)


def make_list_validator(*field_name: str):
    """Get a validator make a list of object if a single object is passed."""

    def split(v: Any):
        if not isinstance(v, list):
            v = [v]
        return v

    return validator(*field_name, allow_reuse=True, pre=True)(split)


def make_list_length_root_validator(
    *field_names,
    length_name: str,
    length_incr: int = 0,
    list_required_with_length: bool = False,
    min_length: int = 0,
):
    """
    Get a root_validator that checks the correct length (and presence) of several list fields in an object.

    Args:
        *field_names (str): names of the instance variables that are a list and need checking.
        length_name (str): name of the instance variable that stores the expected length.
        length_incr (int): Optional extra increment of length value (e.g., to have +1 extra value in lists).
        list_required_with_length (obj:`bool`, optional): Whether each list *must* be present if the length
            attribute is present (and > 0) in the input values. Default: False. If False, list length is only
            checked for the lists that are not None.
        min_length (int): minimum for list length value, overrides length_name value if that is smaller.
            For example, to require list length 1 when length value is given as 0.
    """

    def _get_incorrect_length_validation_message() -> str:
        """Make a string with a validation message, ready to be format()ed with
        field name and length name."""
        incrstring = f" + {length_incr}" if length_incr != 0 else ""
        minstring = f" (and at least {min_length})" if min_length > 0 else ""

        return (
            "Number of values for {} should be equal to the {} value"
            + incrstring
            + minstring
            + "."
        )

    def _validate_listfield_length(
        field_name: str, field: Optional[List[Any]], requiredlength: int
    ):
        """Validate the length of a single field, which should be a list."""

        if field is not None and len(field) != requiredlength:
            raise ValueError(
                _get_incorrect_length_validation_message().format(
                    field_name, length_name
                )
            )
        if field is None and list_required_with_length and requiredlength > 0:
            raise ValueError(
                f"List {field_name} cannot be missing if {length_name} is given."
            )

        return field

    def validate_correct_length(cls, values: dict):
        """The actual validator, will loop across all specified field names in outer function."""
        length = values.get(length_name)
        if length is None:
            # length attribute not present, possibly defer validation to a subclass.
            return values

        requiredlength = max(length + length_incr, min_length)

        for field_name in field_names:
            field = values.get(field_name)
            values[field_name] = _validate_listfield_length(
                field_name, field, requiredlength
            )

        return values

    return root_validator(allow_reuse=True)(validate_correct_length)


def get_forbidden_fields_validator(
    *field_names,
    conditional_field_name: str,
    conditional_value: Any,
    comparison_func: Callable[[Any, Any], bool] = eq,
):
    """
    Gets a validator that checks whether certain fields are *not* provided, if `conditional_field_name` is equal to `conditional_value`.
    The equality check can be overridden with another comparison operator function.

    Args:
        *field_names (str): Names of the instance variables that need to be validated.
        conditional_field_name (str): Name of the instance variable on which the fields are dependent.
        conditional_value (Any): Value that the conditional field should contain to perform this validation.
        comparison_func (Callable): binary operator function, used to override the default "eq" check for the conditional field value.
    """

    def validate_forbidden_fields(cls, values: dict):
        if (val := values.get(conditional_field_name)) is None or not comparison_func(
            val, conditional_value
        ):
            return values

        for field in field_names:
            if values.get(field) != None:
                raise ValueError(
                    f"{field} is forbidden when {conditional_field_name} {operator_str(comparison_func)} {conditional_value}"
                )

        return values

    return root_validator(allow_reuse=True)(validate_forbidden_fields)


def get_required_fields_validator(
    *field_names,
    conditional_field_name: str,
    conditional_value: Any,
    comparison_func: Callable[[Any, Any], bool] = eq,
):
    """
    Gets a validator that checks whether the fields are provided, if `conditional_field_name` is equal to `conditional_value`.
    The equality check can be overridden with another comparison operator function.

    Args:
        *field_names (str): Names of the instance variables that need to be validated.
        conditional_field_name (str): Name of the instance variable on which the fields are dependent.
        conditional_value (Any): Value that the conditional field should contain to perform this validation.
        comparison_func (Callable): binary operator function, used to override the default "eq" check for the conditional field value.
    """

    def validate_required_fields(cls, values: dict):
        if (val := values.get(conditional_field_name)) is None or not comparison_func(
            val, conditional_value
        ):
            return values

        for field in field_names:
            if values.get(field) == None:
                raise ValueError(
                    f"{field} should be provided when {conditional_field_name} {operator_str(comparison_func)} {conditional_value}"
                )

        return values

    return root_validator(allow_reuse=True)(validate_required_fields)


def get_conditional_root_validator(
    root_vldt: classmethod,
    conditional_field_name: str,
    conditional_value: Any,
    comparison_func: Callable[[Any, Any], bool] = eq,
):
    """
    Gets a validator that checks whether certain fields are *not* provided, if `conditional_field_name` is equal to `conditional_value`.
    The equality check can be overridden with another comparison operator function.

    Args:
        root_vldt (classmethod): A root validator that is to be called *if* the condition is satisfied.
        conditional_field_name (str): Name of the instance variable that determines whether the root validator must be called or not.
        conditional_value (Any): Value that the conditional field should be compared with to perform this validation.
        comparison_func (Callable): binary operator function, used to override the default "eq" check for the conditional field value.
    """

    def validate_conditionally(cls, values: dict):
        if (val := values.get(conditional_field_name)) is not None and comparison_func(
            val, conditional_value
        ):
            # Condition is met: call the actual root validator, passing on the attribute values.
            root_vldt.__func__(cls, values)

        return values

    return root_validator(allow_reuse=True)(validate_conditionally)


def get_from_subclass_defaults(cls: Type[BaseModel], fieldname: str, value: str):
    """Gets a value that corresponds with the default field value of one of the subclasses.

    Args:
        cls (Type[BaseModel]): The parent model type.
        fieldname (str): The field name for which retrieve the default for.
        value (str): The value to compare with.

    Returns:
        [type]: The field default that corresponds to the value.
    """
    for c in cls.__subclasses__():
        default = c.__fields__.get(fieldname).default
        if default.lower() == value.lower():
            return default

    return value


class LocationValidationConfiguration(BaseModel):
    """Class that holds the various configuration settings needed for location validation."""

    validate_node: bool = True
    """bool, optional: Whether or not node location specification should be validated. Defaults to True."""

    validate_coordinates: bool = True
    """bool, optional: Whether or not coordinate location specification should be validated. Defaults to True."""

    validate_branch: bool = True
    """bool, optional: Whether or not branch location specification should be validated. Defaults to True."""

    validate_num_coordinates: bool = True
    """bool, optional: Whether or not the number of coordinates should be validated or not. This option is only relevant when `validate_coordinates` is True. Defaults to True."""

    minimum_num_coordinates: int = 0
    """int, optional: The minimum required number of coordinates. This option is only relevant when `validate_coordinates` is True. Defaults to 0."""


class LocationValidationFieldNames(BaseModel):
    """Class that holds the various field names needed for location validation."""

    node_id: str = "nodeId"
    """str, optional: The node id field name. Defaults to `nodeId`."""

    branch_id: str = "branchId"
    """str, optional: The branch id field name. Defaults to `branchId`."""

    chainage: str = "chainage"
    """str, optional: The chainage field name. Defaults to `chainage`."""

    x_coordinates: str = "xCoordinates"
    """str, optional: The x-coordinates field name. Defaults to `xCoordinates`."""

    y_coordinates: str = "yCoordinates"
    """str, optional: The y-coordinates field name. Defaults to `yCoordinates`."""

    num_coordinates: str = "numCoordinates"
    """str, optional: The number of coordinates field name. Defaults to `numCoordinates`."""

    location_type: str = "locationType"
    """str, optional: The location type field name. Defaults to `locationType`."""


def get_location_specification_rootvalidator(
    config: Optional[LocationValidationConfiguration] = None,
    fields: Optional[LocationValidationFieldNames] = None,
):
    """
    Get a root validator that checks for correct location specification in
    typical 1D2D input in an IniBasedModel class.

    Validates for presence of at least one of: nodeId, branchId with chainage,
    xCoordinates with yCoordinates, or xCoordinates with yCoordinates and numCoordinates.
    Validates for the locationType for nodeId and branchId.

    Args:
        config (LocationValidationConfiguration, optional): Configuration for the location validation. Default is None.
        field (LocationValidationFieldNames, optional): Fields names that should be used for the location validation. Default is None.
    """

    if config is None:
        config = LocationValidationConfiguration()

    if fields is None:
        fields = LocationValidationFieldNames()

    def validate_location_specification(cls, values: Dict) -> Dict:
        """
        Verify whether the location given for this object matches the expectations.

        Args:
            values (Dict): Dictionary of object's validated fields.

        Raises:
            ValueError: When exactly one of the following combinations were not given:
            - nodeId
            - branchId with chainage
            - xCoordinates with yCoordinates
            - xCoordinates with yCoordinates and numCoordinates.
            ValueError: When numCoordinates does not meet the requirement minimum amount or does not match the amount of xCoordinates or yCoordinates.
            ValueError: When locationType should be 1d but other was specified.

        Returns:
            Dict: Validated dictionary of input class fields.
        """

        has_node_id = not str_is_empty_or_none(values.get(fields.node_id.lower()))
        has_branch_id = not str_is_empty_or_none(values.get(fields.branch_id.lower()))
        has_chainage = values.get(fields.chainage.lower()) is not None
        has_x_coordinates = values.get(fields.x_coordinates.lower()) is not None
        has_y_coordinates = values.get(fields.y_coordinates.lower()) is not None
        has_num_coordinates = values.get(fields.num_coordinates.lower()) is not None

        # ----- Local validation functions
        def get_length(field: str):
            value = values[field.lower()]
            return len(to_list(value))

        def validate_location_type(expected_location_type: LocationType) -> None:
            location_type = values.get(fields.location_type.lower(), None)
            if str_is_empty_or_none(location_type):
                values[fields.location_type.lower()] = expected_location_type
            elif location_type != expected_location_type:
                raise ValueError(
                    f"{fields.location_type} should be {expected_location_type} but was {location_type}"
                )

        def validate_coordinates_with_num_coordinates() -> None:
            length_x_coordinates = get_length(fields.x_coordinates)
            length_y_coordinates = get_length(fields.y_coordinates)
            num_coordinates = values[fields.num_coordinates.lower()]

            if not num_coordinates == length_x_coordinates == length_y_coordinates:
                raise ValueError(
                    f"{fields.num_coordinates} should be equal to the amount of {fields.x_coordinates} and {fields.y_coordinates}"
                )

            validate_minimum_num_coordinates(num_coordinates)

        def validate_coordinates() -> None:
            len_x_coordinates = get_length(fields.x_coordinates)
            len_y_coordinates = get_length(fields.y_coordinates)

            if len_x_coordinates != len_y_coordinates:
                raise ValueError(
                    f"{fields.x_coordinates} and {fields.y_coordinates} should have an equal amount of coordinates"
                )

            validate_minimum_num_coordinates(len_x_coordinates)

        def validate_minimum_num_coordinates(actual_num: int) -> None:
            if actual_num < config.minimum_num_coordinates:
                raise ValueError(
                    f"{fields.x_coordinates} and {fields.y_coordinates} should have at least {config.minimum_num_coordinates} coordinate(s)"
                )

        def is_valid_node_specification() -> bool:
            has_other = (
                has_branch_id
                or has_chainage
                or has_x_coordinates
                or has_y_coordinates
                or has_num_coordinates
            )
            return has_node_id and not has_other

        def is_valid_branch_specification() -> bool:
            has_other = (
                has_node_id
                or has_x_coordinates
                or has_y_coordinates
                or has_num_coordinates
            )
            return has_branch_id and has_chainage and not has_other

        def is_valid_coordinates_specification() -> bool:
            has_other = (
                has_node_id or has_branch_id or has_chainage or has_num_coordinates
            )
            return has_x_coordinates and has_y_coordinates and not has_other

        def is_valid_coordinates_with_num_coordinates_specification() -> bool:
            has_other = has_node_id or has_branch_id or has_chainage
            return (
                has_x_coordinates
                and has_y_coordinates
                and has_num_coordinates
                and not has_other
            )

        # -----

        error_parts: List[str] = []

        if config.validate_node:
            if is_valid_node_specification():
                validate_location_type(LocationType.oned)
                return values

            error_parts.append(fields.node_id)

        if config.validate_branch:
            if is_valid_branch_specification():
                validate_location_type(LocationType.oned)
                return values

            error_parts.append(f"{fields.branch_id} and {fields.chainage}")

        if config.validate_coordinates:
            if config.validate_num_coordinates:
                if is_valid_coordinates_with_num_coordinates_specification():
                    validate_coordinates_with_num_coordinates()
                    return values

                error_parts.append(
                    f"{fields.x_coordinates}, {fields.y_coordinates} and {fields.num_coordinates}"
                )

            else:
                if is_valid_coordinates_specification():
                    validate_coordinates()
                    return values

                error_parts.append(f"{fields.x_coordinates} and {fields.y_coordinates}")

        error = " or ".join(error_parts) + " should be provided"
        raise ValueError(error)

    return root_validator(allow_reuse=True)(validate_location_specification)

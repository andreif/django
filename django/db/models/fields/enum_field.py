from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import ugettext_lazy as _
from . import Field, PositiveSmallIntegerField

# https://code.djangoproject.com/ticket/24342


try:
    import enum as enum_module
except ImportError:
    enum_module = None


class InvalidEnumValueError(ValidationError):
    pass


class InvalidEnumTypeError(ValidationError):
    pass


class EnumField(Field):
    empty_strings_allowed = False
    default_error_messages = {
        'invalid_value': _('%r is not a valid value for %r enum'),
        'invalid_type': _('%r is configured for %r enum but received %r'),
    }
    description = 'Enum value'

    def __init__(self, enum_class, field_class=PositiveSmallIntegerField, **kwargs):
        self.enum_class = self.validate_enum_class(enum_class)
        self.field_class = self.validate_field_class(field_class)
        # dict(Field.default_error_messages, **)
        self.default_error_messages = dict(
            self.field_class.default_error_messages.copy(),
            **self.default_error_messages
        )
        choices = self.prepare_choices(
            choices=kwargs.pop('choices', None),
            blank=kwargs.get('blank'),
        )
        super(EnumField, self).__init__(choices=choices, **kwargs)

    def validate_enum_class(self, enum_class):
        if not enum_module:
            raise ImportError("enum34 package is required for EnumField")

        if not issubclass(enum_class, enum_module.Enum):
            raise ValueError("enum_class argument must be subclass of enum.Enum")
        return enum_class

    def validate_field_class(self, field_class):
        if not issubclass(field_class, Field):
            raise ValueError("field_class argument must be subclass of Field")
        return field_class

    def prepare_choices(self, choices=None, blank=False):
        choice_option = lambda m: (m.value, m)
        choice_list = lambda itr: list(map(choice_option, itr))
        if choices is not None:
            if isinstance(choices, (list, tuple, set)):
                return choice_list(map(self.enum_class, choices))
        else:
            return choice_list(self.enum_class)

    def get_internal_type(self):
        return "EnumField"

    def deconstruct(self):
        name, path, args, kwargs = super(EnumField, self).deconstruct()
        for k in ['enum_class', 'field_class']:
            del kwargs[k]
        return name, path, args, kwargs

    def validate_value(self, value):
        if value is None:
            if not self.null:
                raise InvalidEnumValueError("")
        elif not isinstance(value, enum_module.Enum):
            try:
                value = self.enum_class(value)
            except ValueError as e:
                err_code = 'invalid_value'
                if 'is not a valid' in str(e):
                    err_msg = self.default_error_messages[err_code] % (value, self.enum_class)
                else:
                    err_msg = e.args[0]
                raise InvalidEnumValueError(message=err_msg, code=err_code, params={'value': value})

        elif not isinstance(value, self.enum_class):
            err_code = 'invalid_type'
            err_msg = self.default_error_messages[err_code] % (self, self.enum_class, type(value))
            raise InvalidEnumTypeError(message=err_msg, code=err_code, params={'value': value})
        return value

    def get_db_prep_value(self, value, connection, prepared=False):
        value = self.validate_enum_value(value)
        # if value is None:
        #     return None
        # if connection.features.has_native_enum_field:
        #     return value
        return value

    def from_db_value(self, value):
        return self.validate_enum_value(value)

    def to_python(self, value):  # validation error
        try:
            return self.validate_enum_value(value)
        except ValidationError:
            raise  # TODO: provide user-friendly messages to views?

    def formfield(self, **kwargs):
        defaults = {
            'form_class': EnumChoiceField,
            'enum_class': self.enum_class,
        }
        defaults.update(kwargs)
        return super(EnumField, self).formfield(**defaults)


class EnumChoiceField(forms.ChoiceField):

    def __init__(self, enum_class, choices=(), **kwargs):
        self.enum_class = enum_class
        super(EnumChoiceField, self).__init__(choices=choices, **kwargs)

    def prepare_value(self, value):
        if isinstance(value, enum_module.Enum):
            return value.value
        return value

    def to_python(self, value):
        value = super(EnumChoiceField, self).to_python(value)
        if value in self.empty_values:
            return None
        if not isinstance(value, enum_module.Enum):
            try:
                value = uuid.UUID(value)
            except ValueError:
                raise ValidationError(self.error_messages['invalid'], code='invalid')
        return value

import warnings

from django import forms
from django.contrib.admin import widgets as admin_widgets
from django.core import checks, exceptions
from django.db import models
from django.utils.functional import SimpleLazyObject
from django.utils.translation import ugettext_lazy as _
from hashids import Hashids

from .conf import settings
from .descriptor import HashidDescriptor
from .hashid import Hashid
from .lookups import HashidIterableLookup, HashidLookup


class HashidFieldMixin(object):
    default_error_messages = {
        'invalid': _("'%(value)s' value must be a positive integer or a valid Hashids string."),
        'invalid_hashid': _("'%(value)s' value must be a valid Hashids string."),
    }
    exact_lookups = ('exact', 'iexact', 'contains', 'icontains')
    iterable_lookups = ('in',)
    passthrough_lookups = ('isnull',)

    def __init__(self, salt=settings.HASHID_FIELD_SALT, min_length=settings.HASHID_FIELD_MIN_LENGTH, alphabet=Hashids.ALPHABET,
                 allow_int_lookup=settings.HASHID_FIELD_ALLOW_INT_LOOKUP, prefix=None, *args, **kwargs):
        self.salt = salt
        self.min_length = min_length
        self.alphabet = alphabet
        self.prefix = prefix
        if 'allow_int' in kwargs:
            warnings.warn("The 'allow_int' parameter was renamed to 'allow_int_lookup'.", DeprecationWarning, stacklevel=2)
            allow_int_lookup = kwargs['allow_int']
            del kwargs['allow_int']
        self.allow_int_lookup = allow_int_lookup
        super(HashidFieldMixin, self).__init__(*args, **kwargs)

    def deconstruct(self):
        name, path, args, kwargs = super(HashidFieldMixin, self).deconstruct()
        kwargs['min_length'] = self.min_length
        kwargs['alphabet'] = self.alphabet
        kwargs['prefix'] = self.prefix
        return name, path, args, kwargs

    def check(self, **kwargs):
        errors = super(HashidFieldMixin, self).check(**kwargs)
        errors.extend(self._check_alphabet_min_length())
        errors.extend(self._check_salt_is_set())
        return errors

    def _check_alphabet_min_length(self):
        if len(self.alphabet) < 16:
            return [
                checks.Error(
                    "'alphabet' must contain a minimum of 16 characters",
                    hint="Add more characters to custom 'alphabet'",
                    obj=self,
                    id='HashidField.E001',
                )
            ]
        return []

    def _check_salt_is_set(self):
        if self.salt is None or self.salt == "":
            return [
                checks.Warning(
                    "'salt' is not set",
                    hint="Pass a salt value in your field or set settings.HASHID_FIELD_SALT",
                    obj=self,
                    id="HashidField.W001",
                )
            ]
        return []

    def encode_id(self, id):
        return Hashid(id, salt=self.salt, min_length=self.min_length, alphabet=self.alphabet, prefix=self.prefix)

    def from_db_value(self, value, expression, connection, context):
        return value

    def get_lookup(self, lookup_name):
        if lookup_name in self.exact_lookups:
            return HashidLookup
        if lookup_name in self.iterable_lookups:
            return HashidIterableLookup
        if lookup_name in self.passthrough_lookups:
            return super(HashidFieldMixin, self).get_lookup(lookup_name)
        return None  # Otherwise, we don't allow lookups of this type

    def to_python(self, value):
        if isinstance(value, Hashid):
            return value
        if value is None:
            return value
        try:
            hashid = self.encode_id(value)
        except ValueError:
            raise exceptions.ValidationError(
                self.error_messages['invalid'],
                code='invalid',
                params={'value': value},
            )
        return hashid

    def get_prep_value(self, value):
        if value is None or value == '':
            return None
        if isinstance(value, Hashid):
            return value.id
        try:
            hashid = self.encode_id(value)
        except ValueError:
            raise ValueError(self.error_messages['invalid'] % {'value': value})
        return hashid.id


class HashidField(HashidFieldMixin, models.IntegerField):
    description = "A Hashids obscured IntegerField"

    def formfield(self, **kwargs):
        defaults = {'form_class': forms.CharField}
        defaults.update(kwargs)
        if defaults.get('widget') == admin_widgets.AdminIntegerFieldWidget:
            defaults['widget'] = admin_widgets.AdminTextInputWidget
        return super(HashidField, self).formfield(**defaults)

    def contribute_to_class(self, cls, name, **kwargs):
        super(HashidField, self).contribute_to_class(cls, name, **kwargs)
        setattr(cls, self.attname, HashidDescriptor(self.attname, salt=self.salt, min_length=self.min_length, alphabet=self.alphabet, prefix=self.prefix))


class HashidAutoField(HashidFieldMixin, models.AutoField):
    description = "A Hashids obscured AutoField"

    def contribute_to_class(self, cls, name, **kwargs):
        super(HashidField, self).contribute_to_class(cls, name, **kwargs)
        setattr(cls, self.attname, HashidDescriptor(self.attname, salt=self.salt, min_length=self.min_length, alphabet=self.alphabet, prefix=self.prefix))


class PrimaryKeyHashidProxyField(HashidFieldMixin, models.IntegerField):

    def contribute_to_class(self, cls, name, **kwargs):
        kwargs['virtual_only'] = True
        super(PrimaryKeyHashidProxyField, self).contribute_to_class(cls, name, **kwargs)
        setattr(cls, self.attname, HashidDescriptor(self.attname, salt=self.salt, min_length=self.min_length, alphabet=self.alphabet, prefix=self.prefix))

        self.column = SimpleLazyObject(lambda: self.model._meta.pk.column)



# Monkey patch Django REST Framework, if it's installed, to throw exceptions if fields aren't explicitly defined in
# ModelSerializers. Not doing so can lead to hard-to-debug behavior.
try:
    from rest_framework.serializers import ModelSerializer
    from hashid_field.rest import UnconfiguredHashidSerialField

    ModelSerializer.serializer_field_mapping[HashidField] = UnconfiguredHashidSerialField
    ModelSerializer.serializer_field_mapping[HashidAutoField] = UnconfiguredHashidSerialField
except ImportError:
    pass

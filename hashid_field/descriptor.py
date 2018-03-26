from hashids import Hashids

from .hashid import Hashid


class HashidDescriptor(object):
    def __init__(self, name, salt='', min_length=0, alphabet=Hashids.ALPHABET, prefix=None):
        self.name = name
        self.salt = salt
        self.min_length = min_length
        self.alphabet = alphabet
        self.prefix = prefix

    def __get__(self, instance, owner=None):
        if instance is not None and self.name in instance.__dict__:
            value = instance.__dict__[self.name]
            return Hashid(value, salt=self.salt, min_length=self.min_length, alphabet=self.alphabet, prefix=self.prefix)
        else:
            return None

    def __set__(self, instance, value):
        if isinstance(value, Hashid) or value is None:
            instance.__dict__[self.name] = value
        else:
            try:
                instance.__dict__[self.name] = Hashid(value, salt=self.salt, min_length=self.min_length, alphabet=self.alphabet, prefix=self.prefix)
            except ValueError:
                instance.__dict__[self.name] = value

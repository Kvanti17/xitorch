import torch
import itertools
from abc import abstractmethod

__all__ = ["CModule", "CParameter"]

class CModule(torch.nn.Module):
    def __init__(self):
        self.__dict__["_cparameters"] = {}
        super(CModule, self).__init__()

    def register(self, x):
        if isinstance(x, torch.Tensor) and not isinstance(x, torch.nn.Parameter):
            return CParameter(x)
        elif isinstance(x, torch.nn.Parameter) or \
             isinstance(x, torch.nn.Module) or \
             isinstance(x, CModule):
            return x
        elif hasattr(x, "__iter__"): # iterable (e.g. list, dict)
            # check is performed in the CParameterList and CParameterDict
            if hasattr(x, "keys"): # mapping
                return CParameterDict(x)
            else:
                return CParameterList(x)
        else:
            raise RuntimeError("Type %s cannot be registered" % type(x))

    def parameters(self, recurse=True, nnparam_only=False):
        for name, val in self.named_parameters(prefix="", recurse=recurse, nnparam_only=nnparam_only):
            yield val

    def named_parameters(self, prefix="", recurse=True, nnparam_only=False):
        memo = set() # set to make sure it returns unique parameters
        for name, v in _param_traverser(self, prefix=prefix, recurse=recurse):
            if v is None or (nnparam_only and not isinstance(v, torch.nn.Parameter)) or v in memo:
                continue
            memo.add(v)
            yield name, v

    ################## __*attr__ functions ##################
    def __setattr__(self, name, value):
        if ("_cparameters" not in self.__dict__):
            raise RuntimeError("__init__() must be called before doing assignments")

        # substituting the old parameters (must retain the type)
        if name in self._cparameters:
            # TODO: decide on what type can substitute the old parameters
            if isinstance(value, torch.Tensor) and not isinstance(value, torch.nn.Parameter):
                self._cparameters[name] = value
            else:
                raise TypeError("Cannot assign type %s to self.%s (torch.Tensor and not torch.nn.Parameter is required)" %\
                    (type(value), name))

        # adding new parameters
        else:
            # TODO: add type
            if isinstance(value, CParameter):
                self._cparameters[name] = value.tensor

            # regular type
            else:
                super(CModule, self).__setattr__(name, value)

    def __getattr__(self, name):
        # called when `name` is not in the usual place
        if name in self._cparameters:
            return self._cparameters[name]

        return super(CModule, self).__getattr__(name)

    def __delattr__(self, name):
        if name in self._cparameters:
            del self._cparameters[name]
            return

        super(CModule, self).__delattr__(name)

def _param_traverser(obj, prefix="", recurse=True):
    # traverse all the parameters of an object (not dropping the duplicate ones)
    # NOTE: this uses torch.nn.Module._parameters attribute, which makes it
    # highly coupled with torch.nn.Module implementation

    def get_members_fcn(module):
        if isinstance(module, CModule):
            return itertools.chain(module._cparameters.items(), module._parameters.items())
        else:
            return module._parameters.items()

    modules = obj.named_modules(prefix=prefix) if recurse else [(prefix, obj)]
    for module_prefix, module in modules:
        members = get_members_fcn(module)
        for k, v in members:
            name = module_prefix + ("." if module_prefix else "") + k
            yield name, v

class CParameter(object):
    # CParameter is needed to differentiate the values that are going to be
    # registered from the ordinary values
    def __init__(self, x):
        if isinstance(x, torch.nn.Parameter):
            raise TypeError("CParameter input cannot be a torch.nn.Parameter")
        self._val = x

    @property
    def tensor(self):
        return self._val

class CParameterList(CModule):
    def __init__(self, xlist):
        super(CParameterList, self).__init__()
        self._cparamlen = len(xlist)
        for i,x in enumerate(xlist):
            if isinstance(x, torch.nn.Module):
                raise TypeError("Please use torch.nn.ModuleList if you want to register a list of module.")
            if not isinstance(x, torch.Tensor):
                raise TypeError("The %d-th element is not a tensor" % i)
            setattr(self, "%d"%i, self.register(x))

    def __getitem__(self, key):
        if key < 0:
            key = key + self._cparamlen
        if key >= self._cparamlen:
            raise IndexError("Cannot access index %d from list with %d elements" % (key, self._cparamlen))
        return getattr(self, "%d"%key)

    def __len__(self):
        return self._cparamlen

class CParameterDict(CModule):
    def __init__(self, xdict):
        super(CParameterDict, self).__init__()
        self._cparamlen = len(xdict)
        self._ckeys = xdict.keys()
        for k,x in xdict.items():
            if isinstance(x, torch.nn.Module):
                raise TypeError("Please use torch.nn.ModuleDict if you want to register a dict of module.")
            if not isinstance(x, torch.Tensor):
                raise TypeError("The %d-th element is not a tensor" % i)
            setattr(self, str(k), self.register(x))

    def __getitem__(self, key):
        if key not in self._ckeys:
            raise KeyError("No %s key in the object" % key)
        return getattr(self, key)

    def __len__(self):
        return self._cparamlen

    def keys(self):
        for k in self._ckeys:
            yield k

    def items(self):
        for k in self._ckeys:
            yield k, self[k]

    def values(self):
        for k in self._ckeys:
            yield self[k]

if __name__ == "__main__":
    class NNModule(torch.nn.Module):
        def __init__(self, a):
            super(NNModule, self).__init__()
            self.a = torch.nn.Parameter(a)

    class NewModule(CModule):
        def __init__(self, a, b):
            super(NewModule, self).__init__()
            self.ab = self.register([a, b])

    class Module2(CModule):
        def __init__(self, amod, at, a):
            super(Module2, self).__init__()
            self.mod = amod
            self.modt = at
            self.a = self.register(a)

    atorch = torch.tensor([1.])
    btorch = torch.tensor([2.])
    a = NewModule(atorch, btorch)
    at = NNModule(atorch)
    a2 = Module2(a, at, torch.nn.Parameter(atorch))
    print(list(a2.named_parameters()))

import contextlib
import torch

def set_default_option(defopt, opt=None):
    if opt is None:
        opt = {}
    defopt.update(opt)
    return defopt

def extract_differentiable_tensors(model):
    res = list(model.parameters())

    # add differentiable and non-parameters attribute in the model
    for varname in model.__dict__:
        var = model.__dict__[varname]
        if not isinstance(var, torch.Tensor): continue
        if var.requires_grad:
            res.append(var)
    return res

@contextlib.contextmanager
def dummy_context_manager():
    yield None

class TensorNonTensorSeparator(object):
    """
    Class that provides function to separate/combine tensors and nontensors
    parameters.
    """
    def __init__(self, params):
        """
        Params is a list of tensor or non-tensor to be splitted into
        tensor/non-tensor
        """
        self.tensor_idxs = []
        self.tensor_params = []
        self.nontensor_idxs = []
        self.nontensor_params = []
        self.nparams = len(params)
        for (i,p) in enumerate(params):
            if isinstance(p, torch.Tensor):
                self.tensor_idxs.append(i)
                self.tensor_params.append(p)
            else:
                self.nontensor_idxs.append(i)
                self.nontensor_params.append(p)
        self.alltensors = len(self.tensor_idxs) == self.nparams

    def get_tensor_params(self):
        return self.tensor_params

    def get_nontensor_params(self):
        return self.nontensor_params

    def get_tensor_idxs(self):
        return self.tensor_idxs

    def get_nontensor_idxs(self):
        return self.nontensor_idxs

    def ntensors(self):
        return len(self.tensor_idxs)

    def nnontensors(self):
        return len(self.nontensor_idxs)

    def reconstruct_params(self, tensor_params, nontensor_params=None):
        if nontensor_params is None:
            nontensor_params = self.nontensor_params
        if len(tensor_params) + len(nontensor_params) != self.nparams:
            raise ValueError("The total length of tensor and nontensor params "\
                "do not match with the expected length: %d instead of %d" % \
                (len(tensor_params)+len(nontensor_params), self.nparams))
        if self.alltensors:
            return tensor_params

        params = [None for _ in range(self.nparams)]
        for nidx,p in zip(self.nontensor_idxs, nontensor_params):
            params[nidx] = p
        for idx,p in zip(self.tensor_idxs, tensor_params):
            params[idx] = p
        return params

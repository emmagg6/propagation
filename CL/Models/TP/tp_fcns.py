'''
Based on code used for the experiments conducted in the submitted paper 
"Fixed-Weight Difference Target Propagation" by K. K. S. Wu, K. C. K. Lee, and T. Poggio.

Adaptation for Continual Learning by emmagg6.

'''

import torch
from torch import nn
from abc import ABCMeta, abstractmethod
from utils import batch_normalization


class abstract_function(metaclass=ABCMeta):
    def __init__(self, in_dim, out_dim, layer, device):
        self.layer = layer
        self.in_dim = in_dim
        self.out_dim = out_dim
        self.device = device

    @abstractmethod
    def forward(self, input, original=None):
        raise NotImplementedError()

    def update(self, lr):
        # Nothing to do
        return

    def zero_grad(self):
        # Nothing to do
        return

    def get_grad(self):
        # Nothing to do
        return None
    
class identity_function(abstract_function):
    def __init__(self, in_dim, out_dim, layer, device, params):
        super().__init__(in_dim, out_dim, layer, device)
        self.weight = torch.eye(out_dim, in_dim, requires_grad=True, device=device)
        if (params["act"] is None) or (params["act"] == "linear"):
            self.activation_function = (lambda x: x)
        elif params["act"] == "linear-BN":
            self.activation_function = (lambda x: batch_normalization(x))
        else:
            raise NotImplementedError()

    def forward(self, input, original=None):
        return self.activation_function(input @ self.weight.T)
    
    def get_params(self):
        # return the parameters
        return {"weight": self.weight.detach().cpu().numpy()}

    def load_params(self, params):
        # load the parameters
        if 'weight' in params:
            self.weight.data.copy_(torch.from_numpy(params['weight']).to(self.device))


class parameterized_function(abstract_function):
    def __init__(self, in_dim, out_dim, layer, device, params):
        super().__init__(in_dim, out_dim, layer, device)
        self.weight = torch.empty(out_dim, in_dim, requires_grad=True, device=device)
        # if params["init"] == "uniform":
        #     nn.init.uniform_(self.weight, -1e-2, 1e-2)
        # elif params["init"] == "gaussian":
        #     nn.init.normal_(self.weight, 0, 1e-3)
        # elif params["init"] == "orthogonal":
        #     nn.init.orthogonal_(self.weight)
        # else:
        #     raise NotImplementedError()
        # TODO: uncomment the above lines, fix, and remove the following line, because now just orthogonal option
        nn.init.orthogonal_(self.weight)

        if params["act"] == "tanh":
            self.activation_function = nn.Tanh()
        elif params["act"] == "linear":
            self.activation_function = (lambda x: x)
        elif params["act"] == "tanh-BN":
            tanh = nn.Tanh()
            self.activation_function = (lambda x: batch_normalization(tanh(x)))
        elif params["act"] == "linear-BN":
            self.activation_function = (lambda x: batch_normalization(x))

    def forward(self, input, original=None):
        return self.activation_function(input @ self.weight.T)

    def update(self, lr):
        self.weight = (self.weight - lr * self.weight.grad).detach().requires_grad_()

    def zero_grad(self):
        if self.weight.grad is not None:
            self.weight.grad.zero_()

    def get_grad(self):
        return self.weight.grad
    
    def get_params(self):
        # Return the weights of the parameterized function
        return {'weight': self.weight.detach().cpu().numpy()}
    
    def load_params(self, params):
        # Assuming 'weight' is the only parameter
        if 'weight' in params:
            self.weight.data.copy_(torch.from_numpy(params['weight']).to(self.device))


class difference_function(abstract_function):
    def __init__(self, in_dim, out_dim, layer, device, params):
        super().__init__(in_dim, out_dim, layer, device)
        if (params["act"] is None) or (params["act"] == "linear"):
            self.activation_function = (lambda x: x)
        elif params["act"] == "linear-BN":
            self.activation_function = (lambda x: batch_normalization(x))
        else:
            raise NotImplementedError()

    def forward(self, input, original=None):
        with torch.no_grad():
            upper = self.layer.forward(original, update=False)
            rec = self.layer.backward_function_1.forward(upper)
            difference = original - rec
        return self.activation_function(input + difference)
    
    def get_params(self):
        # Return the activation function
        return {'weight': None}

    def load_params(self, params):
        # get the activation function
        pass

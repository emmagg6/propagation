'''
Based on code used for the experiments conducted in the submitted paper 
"Fixed-Weight Difference Target Propagation" by K. K. S. Wu, K. C. K. Lee, and T. Poggio.

Adaptation for Continual Learning by emmagg6.

'''

from utils import worker_init_fn, set_seed, combined_loss, set_wandb, set_device
from dataset import make_MNIST, make_FashionMNIST, make_CIFAR10, make_CIFAR100

from Models.BP.bp_nn import bp_net
from Models.TP.tp_nn import tp_net

from initParameters import set_params

import os
import sys
import wandb
import torch
import argparse
import numpy as np
from torch import nn

os.environ['KMP_DUPLICATE_LIB_OK'] = 'True'
BP_LIST = ["BP", "FA", "sFA"]
TP_LIST = ["TP", "DTP", "DTP-BN", "FWDTP", "FWDTP-BN", "ITP", "ITP-BN"]


def get_args():
    parser = argparse.ArgumentParser()

    parser.add_argument("--dataset", type=str, default="MNIST",
                        choices=["MNIST", "FashionMNIST", "CIFAR10", "CIFAR100"])
    parser.add_argument("--algorithm", type=str, default="FWDTP-BN", choices=BP_LIST + TP_LIST)
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--batch_size", type=int, default=256)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--test", action="store_true")

    # model architecture
    parser.add_argument("--depth", type=int, default=6)
    parser.add_argument("--direct_depth", type=int, default=1)
    parser.add_argument("--in_dim", type=int, default=784)
    parser.add_argument("--hid_dim", type=int, default=256)
    parser.add_argument("--out_dim", type=int, default=10)

    parser.add_argument("--learning_rate", "-lr", type=float, default=1e-3)
    parser.add_argument("--learning_rate_backward", "-lrb", type=float, default=1e-3)
    parser.add_argument("--std_backward", "-sb", type=float, default=1e-2)
    parser.add_argument("--stepsize", type=float, default=1e-2)

    parser.add_argument("--label_augmentation", action="store_true")

    # setting of tp_layer
    parser.add_argument("--forward_function_1", "-ff1", type=str, default="parameterized",
                        choices=["random", "parameterized"])
    parser.add_argument("--forward_function_2", "-ff2", type=str, default="parameterized",
                        choices=["random", "parameterized"])
    parser.add_argument("--backward_function_1", "-bf1", type=str, default="parameterized",
                        choices=["random", "parameterized"])
    parser.add_argument("--backward_function_2", "-bf2", type=str, default="parameterized",
                        choices=["random", "difference"])

    # neccesary if {parameterized, random} was choosed
    parser.add_argument("--forward_function_1_init", "-ff1_init", type=str, default="orthogonal",
                        choices=["orthogonal", "gaussian", "uniform"])
    parser.add_argument("--forward_function_2_init", "-ff2_init", type=str, default="orthogonal",
                        choices=["orthogonal", "gaussian", "uniform"])
    parser.add_argument("--backward_function_1_init", "-bf1_init", type=str, default="uniform",
                        choices=["orthogonal", "gaussian", "uniform",
                                 "orthogonal-0", "orthogonal-1", "orthogonal-2", "orthogonal-3", "orthogonal-4",
                                 "gaussian-0", "gaussian-1", "gaussian-1", "gaussian-2", "gaussian-3", "gaussian-4",
                                 "uniform-0", "uniform-1", "uniform-2", "uniform-3", "uniform-4",
                                 "eye-0", "eye-1", "eye-2", "eye-3", "eye-4",
                                 "constant-0", "constant-1", "constant-2", "constant-3", "constant-4",
                                 "rank-1", "rank-2", "rank-4", "rank-8", "same"])
    parser.add_argument("--backward_function_2_init", "-bf2_init", type=str, default="orthogonal",
                        choices=["orthogonal", "gaussian", "uniform"])
    parser.add_argument("--sparse_ratio", "-sr", type=float, default=-1)

    # activation function for bp
    parser.add_argument("--forward_function_1_activation", "-ff1_act", type=str, default="linear-BN",
                        choices=["tanh", "linear", "tanh-BN", "linear-BN"])
    parser.add_argument("--forward_function_2_activation", "-ff2_act", type=str, default="tanh-BN",
                        choices=["tanh", "linear", "tanh-BN", "linear-BN"])
    parser.add_argument("--backward_function_1_activation", "-bf1_act", type=str, default="tanh-BN",
                        choices=["tanh", "linear", "tanh-BN", "linear-BN"])
    parser.add_argument("--backward_function_2_activation", "-bf2_act", type=str, default="linear-BN",
                        choices=["tanh", "linear", "tanh-BN", "linear-BN"])
    parser.add_argument("--forward_last_activation", type=str, default="linear",
                        choices=["tanh", "linear", "tanh-BN", "linear-BN"])

    # loss feedback
    parser.add_argument("--loss_feedback", type=str, default="DTP",
                        choices=["DTP", "DRL", "L-DRL"])
    parser.add_argument("--epochs_backward", type=int, default=5)

    # wandb
    parser.add_argument("--log", action="store_true")
    parser.add_argument("--agent", action="store_true")

    # CL
    parser.add_argument("--continual", type=str, default="no",
                        choices=["no", "yes"])
    # save model params
    parser.add_argument("--save", type=str, default="no",
                        choices=["no", "yes"])

    args = parser.parse_args()
    return args


def main(**kwargs):
    set_seed(kwargs["seed"])
    device = set_device()
    print(f"DEVICE: {device}")

    params = {}

    # Set up the parameters based on the algorithm being used
    if kwargs["algorithm"] in TP_LIST:
        params = set_params(kwargs)  # set_params specific to TP algorithms

    elif kwargs["algorithm"] in BP_LIST:
        params = {
            "ff1": {
                "type": kwargs["forward_function_1"],
                "act": kwargs["forward_function_1_activation"],
                "init": kwargs["forward_function_1_init"]
            },
            "ff2": {
                "type": kwargs["forward_function_2"],
                "act": kwargs["forward_function_2_activation"],
                "init": kwargs["forward_function_2_init"]
            }
        }
    else:
        raise ValueError(f"Unknown algorithm type: {kwargs['algorithm']}")

    # Initialize wandb logging if enabled
    if kwargs["log"]:
        wandb.init(project="propagation-CLtargetprop", config=params)


    ########### DATA ###########
    if kwargs["dataset"] == "MNIST":
        num_classes = 10
        trainset, validset, testset = make_MNIST(kwargs["label_augmentation"],
                                                 kwargs["out_dim"], kwargs["test"])
    elif kwargs["dataset"] == "FashionMNIST":
        num_classes = 10
        trainset, validset, testset = make_FashionMNIST(kwargs["label_augmentation"],
                                                        kwargs["out_dim"], kwargs["test"])
    elif kwargs["dataset"] == "CIFAR10":
        num_classes = 10
        trainset, validset, testset = make_CIFAR10(kwargs["label_augmentation"],
                                                   kwargs["out_dim"], kwargs["test"])
    elif kwargs["dataset"] == "CIFAR100":
        num_classes = 100
        trainset, validset, testset = make_CIFAR100(kwargs["label_augmentation"],
                                                    kwargs["out_dim"], kwargs["test"])
    else:
        raise NotImplementedError()

    if kwargs["label_augmentation"]:
        loss_function = (lambda pred, label: combined_loss(pred, label, device, num_classes))
    else:
        loss_function = nn.CrossEntropyLoss(reduction="sum")

    # Set the loss function
    if kwargs["label_augmentation"]:
        loss_function = lambda pred, label: combined_loss(pred, label, device, num_classes)
    else:
        loss_function = nn.CrossEntropyLoss(reduction="sum")


    # make dataloader
    train_loader = torch.utils.data.DataLoader(trainset,
                                               batch_size=kwargs["batch_size"],
                                               shuffle=True,
                                               num_workers=2,
                                               pin_memory=True,
                                               worker_init_fn=worker_init_fn)
    valid_loader = torch.utils.data.DataLoader(validset,
                                               batch_size=kwargs["batch_size"],
                                               shuffle=False,
                                               num_workers=2,
                                               pin_memory=True,
                                               worker_init_fn=worker_init_fn)
    test_loader = torch.utils.data.DataLoader(testset,
                                              batch_size=kwargs["batch_size"],
                                              shuffle=False,
                                              num_workers=2,
                                              pin_memory=True,
                                              worker_init_fn=worker_init_fn)




    ######### MODEL ###########
    if kwargs["algorithm"] in BP_LIST:
        # Instantiate the bp_net model with the appropriate arguments
        model = bp_net(kwargs["depth"], kwargs["in_dim"], kwargs["hid_dim"],
                       kwargs["out_dim"], loss_function, device, params=params)

        # If continual learning is enabled, load the saved model parameters
        if kwargs["continual"] == "yes":
            # model.load_state_dict(torch.load("checkpoints/bp/BP-m-f.pth"))
            model.load_state("checkpoints/bp/BP-m-same.pth", kwargs["learning_rate"] )

        # Train the model
        model.train_model(train_loader, valid_loader, kwargs["epochs"], kwargs["learning_rate"], kwargs["log"], kwargs["save"])

    elif kwargs["algorithm"] in TP_LIST:        
         # initialize model
        model = tp_net(kwargs["depth"], kwargs["direct_depth"], kwargs["in_dim"],
                       kwargs["hid_dim"], kwargs["out_dim"], loss_function, device, params=params)
        
        # If continual learning is enabled, load the saved model parameters
        if kwargs["continual"] == "yes":
            saved_state = torch.load("checkpoints/tp/FWDTP-mnist.pth")
            model.load_state(saved_state)
        
        # train
        model.train(train_loader, valid_loader, kwargs["epochs"], kwargs["learning_rate"],
                    kwargs["learning_rate_backward"], kwargs["std_backward"], kwargs["stepsize"],
                    kwargs["log"], {"loss_feedback": kwargs["loss_feedback"], "epochs_backward": kwargs["epochs_backward"]}, kwargs["save"])


    # Test the model
    loss, acc = model.external_test(test_loader)
    print(f"Test Loss      : {loss}")
    if acc is not None:
        print(f"Test Acc       : {acc}")

# Entry point for the script
if __name__ == '__main__':
    FLAGS = get_args()
    main(**vars(FLAGS))








'''
def main(**kwargs):
    set_seed(kwargs["seed"])
    device = set_device()
    print(f"DEVICE: {device}")

    if kwargs["save"] == 'yes':
        track = True
    else:
        track = False


    if kwargs["algorithm"] in TP_LIST:
            params = set_params(kwargs)
            print("Forward  : ", end="")
            print(f"{params['ff1']['type']}({params['ff1']['act']},{params['ff1']['init']})", end="")
            print(f" -> {params['ff2']['type']}({params['ff2']['act']},{params['ff2']['init']})")
            print("Backward : ", end="")
            print(f"{params['bf1']['type']}({params['bf1']['act']},{params['bf1']['init']})", end="")
            print(f" -> {params['bf2']['type']}({params['bf2']['act']},{params['bf2']['init']})")
            if kwargs["log"]:
                set_wandb(kwargs, params)
    elif kwargs["algorithm"] in BP_LIST:
            print("Forward  : ", end="")
            print(f"{kwargs['forward_function_2_activation']}, orthogonal")
            if kwargs["log"]:
                config = kwargs.copy()
                config["activation_function"] = kwargs['forward_function_2_activation']
                wandb.init(config=config)


    ########### DATA ###########
    if kwargs["dataset"] == "MNIST":
        num_classes = 10
        trainset, validset, testset = make_MNIST(kwargs["label_augmentation"],
                                                 kwargs["out_dim"], kwargs["test"])
    elif kwargs["dataset"] == "FashionMNIST":
        num_classes = 10
        trainset, validset, testset = make_FashionMNIST(kwargs["label_augmentation"],
                                                        kwargs["out_dim"], kwargs["test"])
    elif kwargs["dataset"] == "CIFAR10":
        num_classes = 10
        trainset, validset, testset = make_CIFAR10(kwargs["label_augmentation"],
                                                   kwargs["out_dim"], kwargs["test"])
    elif kwargs["dataset"] == "CIFAR100":
        num_classes = 100
        trainset, validset, testset = make_CIFAR100(kwargs["label_augmentation"],
                                                    kwargs["out_dim"], kwargs["test"])
    else:
        raise NotImplementedError()

    if kwargs["label_augmentation"]:
        loss_function = (lambda pred, label: combined_loss(pred, label, device, num_classes))
    else:
        loss_function = nn.CrossEntropyLoss(reduction="sum")

    # make dataloader
    train_loader = torch.utils.data.DataLoader(trainset,
                                               batch_size=kwargs["batch_size"],
                                               shuffle=True,
                                               num_workers=2,
                                               pin_memory=True,
                                               worker_init_fn=worker_init_fn)
    valid_loader = torch.utils.data.DataLoader(validset,
                                               batch_size=kwargs["batch_size"],
                                               shuffle=False,
                                               num_workers=2,
                                               pin_memory=True,
                                               worker_init_fn=worker_init_fn)
    test_loader = torch.utils.data.DataLoader(testset,
                                              batch_size=kwargs["batch_size"],
                                              shuffle=False,
                                              num_workers=2,
                                              pin_memory=True,
                                              worker_init_fn=worker_init_fn)

   
   ######### MODEL ###########
    if kwargs["algorithm"] in BP_LIST:
        if kwargs["continual"] == "yes":
            cont = True
        else: 
            cont = False

        model = bp_net(kwargs["depth"], kwargs["in_dim"], kwargs["hid_dim"],
                       kwargs["out_dim"], kwargs["forward_function_2_activation"],
                       loss_function, kwargs["algorithm"], device, continual=cont)
        # If continual learning is enabled, load the saved model parameters
        if cont:
            model.load_model(path = "checkpoints/bp/BP-now.pth")

        model.train(train_loader, valid_loader, kwargs["epochs"], kwargs["learning_rate"],
                    kwargs["log"], kwargs["save"])
        # model.train_model(train_loader, valid_loader, kwargs["epochs"], kwargs["learning_rate"], kwargs["log"], kwargs["save"])
    elif kwargs["algorithm"] in TP_LIST:        
         # initialize model
        model = tp_net(kwargs["depth"], kwargs["direct_depth"], kwargs["in_dim"],
                       kwargs["hid_dim"], kwargs["out_dim"], loss_function, device, params=params)
        
        # If continual learning is enabled, load the saved model parameters
        if kwargs["continual"] == "yes":
            saved_state = torch.load("checkpoints/tp/FWDTP-mnist.pth")
            model.load_state(saved_state)
        
        # train
        model.train(train_loader, valid_loader, kwargs["epochs"], kwargs["learning_rate"],
                    kwargs["learning_rate_backward"], kwargs["std_backward"], kwargs["stepsize"],
                    kwargs["log"], {"loss_feedback": kwargs["loss_feedback"], "epochs_backward": kwargs["epochs_backward"]}, kwargs["save"])

    # test
    loss, acc = model.test(test_loader)
    print(f"Test Loss      : {loss}")
    if acc is not None:
        print(f"Test Acc       : {acc}")


if __name__ == '__main__':
    FLAGS = vars(get_args())
    main(**FLAGS)
'''
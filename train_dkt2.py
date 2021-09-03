import argparse
import pandas as pd
from random import shuffle
from sklearn.metrics import roc_auc_score, accuracy_score

import torch.nn as nn
from torch.optim import Adam
from torch.nn.utils.rnn import pad_sequence

from model_dkt2 import DKT2
from utils import *
import sys
import gc

def repackage_hidden(h):
    """Wraps hidden states in new Tensors, to detach them from their history."""
    if isinstance(h, torch.Tensor):
        return h.detach()
    else:
        return tuple(repackage_hidden(v) for v in h)

def get_data(df, train_split=0.8, randomize=True):
    """Extract sequences from dataframe.

    Arguments:
        df (pandas Dataframe): output by prepare_data.py
        train_split (float): proportion of data to use for training
    """
    item_ids = [torch.tensor(u_df["item_id"].values, dtype=torch.long)
                for _, u_df in df.groupby("user_id")]
    skill_ids = [torch.tensor(u_df["skill_id"].values, dtype=torch.long)
                 for _, u_df in df.groupby("user_id")]
    labels = [torch.tensor(u_df["correct"].values, dtype=torch.long)
              for _, u_df in df.groupby("user_id")]
    # item_ids = [u_df["item_id"].values
    #             for _, u_df in df.groupby("user_id")]
    # skill_ids = [u_df["skill_id"].values
    #              for _, u_df in df.groupby("user_id")]
    # labels = [u_df["correct"].values
    #           for _, u_df in df.groupby("user_id")]

    item_inputs = [torch.cat((torch.zeros(1, dtype=torch.long), i))[:-1] for i in item_ids]
    skill_inputs = [torch.cat((torch.zeros(1, dtype=torch.long), s))[:-1] for s in skill_ids]
    label_inputs = [torch.cat((torch.zeros(1, dtype=torch.long), l))[:-1] for l in labels]

    # item_ids.cpu()
    # skill_ids.cpu()
    # labels.cpu()
    # item_inputs.cpu()
    # skill_inputs.cpu()
    # label_inputs.cpu()

    for i in item_ids:
        i = i.cpu()

    for i in skill_ids:
        i = i.cpu()

    for i in labels:
        i = i.cpu()

    for i in item_inputs:
        i = i.cpu()

    for i in skill_inputs:
        i = i.cpu()

    for i in labels:
        i = i.cpu()
    torch.cuda.empty_cache()
    data = list(zip(item_inputs, skill_inputs, label_inputs, item_ids, skill_ids, labels))
    if randomize:
        shuffle(data)

    # Train-test split across users
    train_size = int(train_split * len(data))
    train_data, val_data = data[:train_size], data[train_size:]
    return train_data, val_data


def prepare_batches(data, batch_size, randomize=True):
    """Prepare batches grouping padded sequences.

    Arguments:
        data (list of lists of torch Tensor): output by get_data
        batch_size (int): number of sequences per batch

    Output:
        batches (list of lists of torch Tensor)
    """
    if randomize:
        shuffle(data)
    batches = []

    for k in range(0, len(data), batch_size):
        batch = data[k:k + batch_size]
        seq_lists = list(zip(*batch))
        inputs_and_ids = [pad_sequence(seqs, batch_first=True, padding_value=0)
                          for seqs in seq_lists[:-1]]
        labels = pad_sequence(seq_lists[-1], batch_first=True, padding_value=-1)  # Pad labels with -1
        batches.append([*inputs_and_ids, labels])

    return batches


def compute_auc(preds, labels):
    preds = preds[labels >= 0].flatten()
    labels = labels[labels >= 0].float()
    if len(torch.unique(labels)) == 1:  # Only one class
        auc = accuracy_score(labels, preds.round())
    else:
        auc = roc_auc_score(labels, preds)
    return auc


def compute_loss(preds, labels, criterion):
    preds = preds[labels >= 0].flatten()
    labels = labels[labels >= 0].float()
    return criterion(preds, labels)


# def train(train_data, val_data, model, optimizer, logger, saver, num_epochs, batch_size):
def train(model, train_batches, val_batches, batch_size, epoch):
    """Train DKT model.

    Arguments:
        train_data (list of lists of torch Tensor)
        val_data (list of lists of torch Tensor)
        model (torch Module)
        optimizer (torch optimizer)
        logger: wrapper for TensorboardX logger
        saver: wrapper for torch saving
        num_epochs (int): number of epochs to train for
        batch_size (int)
    """
    # criterion = nn.BCEWithLogitsLoss()
    # metrics = Metrics()
    # step = 0

    # for epoch in range(num_epochs):
    #     train_batches = prepare_batches(train_data, batch_size)
    #     val_batches = prepare_batches(val_data, batch_size)
    #     total_loss = 0

        # Training
        # for item_inputs, skill_inputs, label_inputs, item_ids, skill_ids, labels in train_batches:
    total_loss  =0
    step = 0
    hidden = model.init_hidden(batch_size)
    total_batches = len(train_batches) // batch_size

    for i in range(len(train_batches)):
        item_inputs, skill_inputs, label_inputs, item_ids, skill_ids, labels = train_batches[i]

        # item_inputs = torch.tensor(item_inputs, dtype=torch.int64)
        # skill_inputs = torch.tensor(skill_inputs, dtype=torch.int64)
        # label_inputs = torch.tensor(label_inputs, dtype=torch.int64)
        # item_ids = torch.tensor(item_ids, dtype=torch.int64)
        # skill_ids = torch.tensor(skill_ids, dtype=torch.int64)
        # labels = torch.tensor(labels, dtype=torch.int64)
        

        item_inputs = item_inputs.cuda()
        skill_inputs=skill_inputs.cuda()
        label_inputs=label_inputs.cuda()
        item_ids=item_ids.cuda()
        skill_ids=skill_ids.cuda()
        # labels=labels.cuda()

        model.train()
        hidden = repackage_hidden(hidden)

        optimizer.zero_grad()

        
        print("before train")
        preds, hidden = model(item_inputs, skill_inputs, label_inputs, item_ids, skill_ids, hidden)
        print("after train")
        item_inputs = item_inputs.cpu()
        skill_inputs=skill_inputs.cpu()
        label_inputs=label_inputs.cpu()
        item_ids=item_ids.cpu()
        skill_ids=skill_ids.cpu()
        loss = compute_loss(preds, labels.cuda(), criterion)
        train_auc = compute_auc(torch.sigmoid(preds).detach().cpu(), labels)

        print("before back")
        loss.backward()
        print("after back")
        optimizer.step()
        step += 1
        # metrics.store({'loss/train': loss.item()})
        # metrics.store({'auc/train': train_auc})
        total_loss += loss.item()
        # Logging
        if step % 20 == 0:
            # logger.log_scalars(metrics.average(), step, epoch=epoch)
            print(epoch, step, total_batches*len(item_ids), total_loss, train_auc)
            

    # Validation
    print("eval")
    model.eval()
    for item_inputs, skill_inputs, label_inputs, item_ids, skill_ids, labels in val_batches:
        with torch.no_grad():
            item_inputs = item_inputs.cuda()
            skill_inputs = skill_inputs.cuda()
            label_inputs = label_inputs.cuda()
            item_ids = item_ids.cuda()
            skill_ids = skill_ids.cuda()
            preds, hidden = model(item_inputs, skill_inputs, label_inputs, item_ids, skill_ids, hidden)
        val_auc = compute_auc(torch.sigmoid(preds).cpu(), labels)
        metrics.store({'auc/val': val_auc})
        hidden = repackage_hidden(hidden)
    model.train()

    
    # Save model
    # average_metrics = metrics.average()
    # logger.log_scalars(average_metrics, step)
    # stop = saver.save(average_metrics['auc/val'], model)
    average_metrics = 0
    stop = False

    return average_metrics, stop, total_loss
        


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Train DKT.')
    parser.add_argument('--dataset', type=str)
    parser.add_argument('--logdir', type=str, default='runs/dkt')
    parser.add_argument('--savedir', type=str, default='save/dkt')
    parser.add_argument('--hid_size', type=int, default=200)
    parser.add_argument('--embed_size', type=int, default=200)
    parser.add_argument('--num_hid_layers', type=int, default=1)
    parser.add_argument('--drop_prob', type=float, default=0.5)
    parser.add_argument('--batch_size', type=int, default=32)
    parser.add_argument('--lr', type=float, default=1e-2)
    parser.add_argument('--num_epochs', type=int, default=100)
    parser.add_argument('--seed', type=int, default=0)
    args = parser.parse_args()

    set_random_seeds(args.seed)

    full_df = pd.read_csv(os.path.join('data', args.dataset, 'preprocessed_data.csv'), sep="\t")
    train_df = pd.read_csv(os.path.join('data', args.dataset, 'preprocessed_data_train.csv'), sep="\t")
    test_df = pd.read_csv(os.path.join('data', args.dataset, 'preprocessed_data_test.csv'), sep="\t")

    train_data, val_data = get_data(train_df, train_split=0.8)

    model = DKT2(int(full_df["item_id"].max()), int(full_df["skill_id"].max()), args.hid_size,
                 args.embed_size, args.num_hid_layers, args.drop_prob).cuda()
    optimizer = Adam(model.parameters(), lr=args.lr)
    # Reduce batch size until it fits on GPU
    while True:
        try:
            # Train
            torch.cuda.empty_cache()
            param_str = f"{args.dataset}"
            logger = Logger(os.path.join(args.logdir, param_str))
            saver = Saver(args.savedir, param_str)
            # train(train_data, val_data, model, optimizer, logger, saver, args.num_epochs, args.batch_size)
            criterion = nn.BCEWithLogitsLoss()
            metrics = Metrics()
            step = 0

            
            train_batches = prepare_batches(train_data, args.batch_size)
            val_batches = prepare_batches(val_data, args.batch_size)
            for epoch in range(args.num_epochs):
                average_metrics, stop, total_loss = train(model, train_batches, val_batches, args.batch_size, epoch)

            if stop:
                break

            break
        except RuntimeError as err:
            print(err)
            args.batch_size = args.batch_size // 2
            print(f'Batch does not fit on gpu, reducing size to {args.batch_size}')
            break
    
    logger.close()

    model = saver.load()
    test_data, _ = get_data(test_df, train_split=1.0, randomize=False)
    test_batches = prepare_batches(test_data, args.batch_size, randomize=False)
    test_preds = np.empty(0)

    # Predict on test set
    model.eval()
    for item_inputs, skill_inputs, label_inputs, item_ids, skill_ids, labels in test_batches:
        with torch.no_grad():
            item_inputs = item_inputs.cuda()
            skill_inputs = skill_inputs.cuda()
            label_inputs = label_inputs.cuda()
            item_ids = item_ids.cuda()
            skill_ids = skill_ids.cuda()
            preds = model(item_inputs, skill_inputs, label_inputs, item_ids, skill_ids)
            preds = torch.sigmoid(preds[labels >= 0]).cpu().numpy()
            test_preds = np.concatenate([test_preds, preds])

    # Write predictions to csv
    test_df["DKT2"] = test_preds
    test_df.to_csv(f'data/{args.dataset}/preprocessed_data_test.csv', sep="\t", index=False)

    print("auc_test = ", roc_auc_score(test_df["correct"], test_preds))



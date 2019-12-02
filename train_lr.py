from sklearn.metrics import roc_auc_score, accuracy_score, log_loss, brier_score_loss
from sklearn.linear_model import LogisticRegression
from scipy.sparse import load_npz, csr_matrix
import argparse
import numpy as np


def compute_metrics(y_pred, y):
    acc = accuracy_score(y, np.round(y_pred))
    auc = roc_auc_score(y, y_pred)
    nll = log_loss(y, y_pred)
    mse = brier_score_loss(y, y_pred)
    return acc, auc, nll, mse


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Train logistic regression on sparse feature matrix.')
    parser.add_argument('--X_file', type=str)
    parser.add_argument('--dataset', type=str)
    parser.add_argument('--iter', type=int, default=1000)
    args = parser.parse_args()

    features_suffix = (args.X_file.split("-")[-1]).split(".")[0]

    # Load sparse dataset
    X = csr_matrix(load_npz(args.X_file))
    
    # Student-level train-val split
    user_ids = X[:, 0].toarray().flatten()
    users = np.unique(user_ids)
    np.random.shuffle(users)
    split = int(0.8 * len(users))
    users_train, users_val = users[:split], users[split:]
    train = X[np.where(np.isin(user_ids, users_train))]
    val = X[np.where(np.isin(user_ids, users_val))]
    
    # First 5 columns are the original dataset including label in column 3
    X_train, y_train = train[:, 5:], train[:, 3].toarray().flatten()
    X_val, y_val = val[:, 5:], val[:, 3].toarray().flatten()
    
    model = LogisticRegression(solver="lbfgs", max_iter=args.iter)
    model.fit(X_train, y_train)
    
    # Compute metrics
    y_pred_train = model.predict_proba(X_train)[:, 1]
    y_pred_val = model.predict_proba(X_val)[:, 1]
    acc_train, auc_train, nll_train, mse_train = compute_metrics(y_pred_train, y_train)
    acc_val, auc_val, nll_val, mse_val = compute_metrics(y_pred_val, y_val)
    print(f"{args.dataset}, {features_suffix},"
          f"auc={auc_train}(train)/{auc_val}(val),"
          f"mse={mse_train}(train)/{mse_val}(val)")

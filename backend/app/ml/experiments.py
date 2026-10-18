"""Offline, leakage-aware application-security experiments. Never imported by the API."""
import argparse, hashlib, json, platform, time
from pathlib import Path
import joblib, numpy as np, pandas as pd, sklearn
from threadpoolctl import threadpool_limits
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier, IsolationForest, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import average_precision_score, confusion_matrix, f1_score, precision_recall_fscore_support
from sklearn.model_selection import StratifiedShuffleSplit
from sklearn.pipeline import Pipeline
from .application_detection import FEATURES

SEED=42017
def checksum(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def paths(root):
    root.mkdir(parents=True,exist_ok=True); return {name:root/f"{name}.csv" for name in ("train","validation","test")}

def prepare(source:Path,work:Path):
    data=pd.read_csv(source); required=set(FEATURES+["label"])
    if not required.issubset(data.columns): raise ValueError(f"Missing columns: {sorted(required-set(data.columns))}")
    if "synthetic_run_id" in data.columns:
        raise ValueError("Group-aware split is required for synthetic_run_id datasets; the toy fixture intentionally has no run groups")
    first=StratifiedShuffleSplit(n_splits=1,test_size=.4,random_state=SEED); train_i,rest_i=next(first.split(data,data.label)); rest=data.iloc[rest_i]
    second=StratifiedShuffleSplit(n_splits=1,test_size=.5,random_state=SEED+1);val_i,test_i=next(second.split(rest,rest.label))
    split={"train":data.iloc[train_i],"validation":rest.iloc[val_i],"test":rest.iloc[test_i]}
    for name,frame in split.items(): frame.to_csv(paths(work)[name],index=False)
    (work/"split.json").write_text(json.dumps({"seed":SEED,"strategy":"stratified holdout; no time/device/session fields exist in toy fixture","source_sha256":checksum(source),"rows":{k:len(v) for k,v in split.items()},"warning":"40-row synthetic toy fixture; no generalization claim"},indent=2))

def risk(proba,classes): return np.array([sum(p for p,c in zip(row,classes) if int(c)!=0) for row in proba])
def threshold(y,score):
    candidates=np.unique(score); best=(.5,-1.)
    binary=(y!=0).astype(int)
    for value in candidates:
        metric=f1_score(binary,(score>=value).astype(int),zero_division=0)
        if metric>best[1]: best=(float(value),float(metric))
    return best
def pipeline(model): return Pipeline([("imputer",SimpleImputer(strategy="median")),("model",model)])

def train(work:Path):
    train=pd.read_csv(paths(work)["train"]);val=pd.read_csv(paths(work)["validation"]);X,y=train[FEATURES].to_numpy(),train.label.to_numpy();Xv,yv=val[FEATURES].to_numpy(),val.label.to_numpy()
    models={"random_forest":pipeline(RandomForestClassifier(n_estimators=400,class_weight="balanced",random_state=SEED,n_jobs=1)),"hist_gradient_boosting":pipeline(HistGradientBoostingClassifier(max_iter=250,l2_regularization=1.,random_state=SEED))}
    summary={}
    for name,model in models.items():
        with threadpool_limits(limits=1): model.fit(X,y)
        pred=model.predict(Xv);score=risk(model.predict_proba(Xv),model.classes_);cut,binary_f1=threshold(yv,score);summary[name]={"macro_f1":f1_score(yv,pred,average="macro"),"threshold":cut,"validation_binary_f1":binary_f1};joblib.dump(model,work/f"{name}.joblib")
    winner=max(summary,key=lambda n:summary[n]["macro_f1"]);normal=X[y==0]
    isolation=pipeline(IsolationForest(n_estimators=300,contamination="auto",random_state=SEED,n_jobs=1));isolation.fit(normal)
    normal_val=Xv[yv==0];novelty=-isolation.decision_function(normal_val); novelty_threshold=float(np.quantile(novelty,.95)) if len(novelty) else 0.
    joblib.dump({"classifier":models[winner],"isolation":isolation,"threshold":summary[winner]["threshold"],"novelty_threshold":novelty_threshold,"model_version":f"application-{winner}-v1"},work/"bundle.joblib")
    (work/"validation.json").write_text(json.dumps({"selection_metric":"macro_f1","selected":winner,"candidates":summary,"novelty_score_direction":"higher (-decision_function) is more anomalous","novelty_threshold":novelty_threshold},indent=2))

def evaluate(work:Path,out:Path):
    bundle=joblib.load(work/"bundle.joblib");test=pd.read_csv(paths(work)["test"]);X,y=test[FEATURES].to_numpy(),test.label.to_numpy();model=bundle["classifier"]
    start=time.perf_counter_ns();proba=model.predict_proba(X);elapsed=(time.perf_counter_ns()-start)/1e6;pred=model.predict(X);score=risk(proba,model.classes_);binary=(y!=0).astype(int);binary_pred=(score>=bundle["threshold"]).astype(int);p,r,f,s=precision_recall_fscore_support(y,pred,labels=[0,1,2,3],zero_division=0);tn,fp,fn,tp=confusion_matrix(binary,binary_pred,labels=[0,1]).ravel()
    individual=[]
    for row in X:
        t=time.perf_counter_ns();model.predict_proba(np.array([row]));individual.append((time.perf_counter_ns()-t)/1e6)
    predictions=pd.DataFrame({"actual":y,"predicted":pred,"attack_score":score,"binary_predicted":binary_pred});out.mkdir(parents=True,exist_ok=True);predictions.to_csv(out/"predictions.csv",index=False)
    report={"evaluation_status":"FINAL_HELD_OUT_TOY_FIXTURE","warning":"Tiny synthetic fixture; results do not establish deployment generalization.","model_version":bundle["model_version"],"schema_version":"application-security-v1","dataset_checksums":{"source":json.loads((work/"split.json").read_text())["source_sha256"],"test":checksum(paths(work)["test"])},"seed":SEED,"versions":{"python":platform.python_version(),"sklearn":sklearn.__version__,"numpy":np.__version__,"pandas":pd.__version__},"hardware":{"machine":platform.machine(),"processor":platform.processor(),"platform":platform.platform()},"class_support":{str(i):int(s[n]) for n,i in enumerate([0,1,2,3])},"macro_f1":f1_score(y,pred,average="macro"),"per_class":{str(i):{"precision":float(p[n]),"recall":float(r[n])} for n,i in enumerate([0,1,2,3])},"confusion_matrix":confusion_matrix(y,pred,labels=[0,1,2,3]).tolist(),"binary_attack_pr_auc":average_precision_score(binary,score),"false_positive_rate":float(fp/(fp+tn)) if fp+tn else None,"threshold":bundle["threshold"],"score_direction":"higher attack_score means greater estimated attack risk","inference_latency_ms":{"batch_total":elapsed,"p50":float(np.percentile(individual,50)),"p95":float(np.percentile(individual,95))}}
    (out/"evaluation.json").write_text(json.dumps(report,indent=2));joblib.dump(bundle,out/"application_detector.joblib");(out/"schema.json").write_text(json.dumps({"version":"application-security-v1","features":FEATURES},indent=2));(out/"manifest.json").write_text(json.dumps({"artifact":"application_detector.joblib","report":"evaluation.json","schema":"schema.json"},indent=2))

def main():
    parser=argparse.ArgumentParser();parser.add_argument("command",choices=["prepare","train","evaluate","all"]);parser.add_argument("--source",type=Path,default=Path("datasets/healthcare_ids_dataset.csv"));parser.add_argument("--work",type=Path,default=Path("backend/app/ml/work"));parser.add_argument("--out",type=Path,default=Path("backend/app/ml/artifacts"));args=parser.parse_args()
    if args.command in ("prepare","all"):prepare(args.source,args.work)
    if args.command in ("train","all"):train(args.work)
    if args.command in ("evaluate","all"):evaluate(args.work,args.out)
if __name__=="__main__":main()

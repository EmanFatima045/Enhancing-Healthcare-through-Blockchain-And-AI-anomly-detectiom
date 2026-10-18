"""Optional CICIoMT2024 ingestion; no download and no clinical-label fabrication."""
import argparse,json
from pathlib import Path
import pandas as pd
NETWORK_FEATURES=["flow_duration","header_length","protocol_type","duration","rate","srate","drate","fin_flag_number","syn_flag_number","rst_flag_number","psh_flag_number","ack_flag_number","ece_flag_number","cwr_flag_number","ack_count","syn_count","fin_count","urg_count","rst_count","http","https","dns","telnet","smtp","ssh","irc","tcp","udp","dhcp","arp","icmp","ipv","llc","tot_sum","min","max","avg","std","tot_size","iat","number","variance"]
def ingest(root:Path,out:Path,accept_terms:bool):
    if not root.exists():return {"status":"NOT_RUN","reason":"Place extracted CICIoMT2024 CSV files in datasets/ciciomt2024/raw"}
    terms=root.parent/"LICENSE_OR_TERMS.txt"
    if not accept_terms or not terms.exists():raise RuntimeError("Review official UNB terms, save LICENSE_OR_TERMS.txt, and pass --accept-terms")
    files=sorted(root.rglob("*.csv"))
    if not files:return {"status":"NOT_RUN","reason":"No CSV files found"}
    frames=[]
    for path in files:
        frame=pd.read_csv(path);frame.columns=[c.strip().lower().replace(" ","_") for c in frame.columns];missing=[c for c in NETWORK_FEATURES+["label"] if c not in frame.columns]
        if missing:raise ValueError(f"{path.name}: schema mismatch; missing {missing}")
        frames.append(frame[NETWORK_FEATURES+["label"]])
    combined=pd.concat(frames,ignore_index=True);out.parent.mkdir(parents=True,exist_ok=True);combined.to_parquet(out,index=False);return {"status":"PREPARED_NOT_EVALUATED","rows":len(combined),"output":str(out),"domain":"IoMT network traffic only"}
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--root",type=Path,default=Path("datasets/ciciomt2024/raw"));p.add_argument("--out",type=Path,default=Path("datasets/ciciomt2024/prepared/network.parquet"));p.add_argument("--accept-terms",action="store_true");a=p.parse_args();print(json.dumps(ingest(a.root,a.out,a.accept_terms),indent=2))

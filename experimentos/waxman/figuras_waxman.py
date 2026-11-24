import csv, statistics, matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
plt.rcParams["font.family"]="DejaVu Sans"
r=list(csv.DictReader(open("/mnt/user-data/uploads/Capstone/Capstone-G22/experimentos/waxman/corridas.csv",encoding="utf-8")))
C={"4":"#1C7293","8":"#F2A541"}
fig,(a,b)=plt.subplots(1,2,figsize=(11.2,4.3))
for g in ("4","8"):
    med=[]
    for n in (200,400,800):
        v=[float(x["tiempo_interno_s"]) for x in r if x["eta"]=="25" and x["familia"]==f"waxman_g{g}_n{n}"]
        a.scatter([n]*len(v),v,color=C[g],s=28,alpha=.75,zorder=3); med.append(statistics.median(v))
    a.plot((200,400,800),med,color=C[g],lw=2,label=f"Grado {g} (mediana)")
a.set_xscale("log");a.set_yscale("log");a.set_xticks([200,400,800]);a.set_xticklabels(["200","400","800"])
a.set_xlabel("Nodos");a.set_ylabel("Tiempo interno (s), η = 25");a.set_title("Tamaño: cada punto es una semilla",fontsize=10.5,loc="left")
a.legend(frameon=False,fontsize=8.5);a.grid(alpha=.25,which="both")
inst=sorted({x["instancia"] for x in r if x["eta"]=="0"})
for i in inst:
    t={int(x["eta"]):float(x["tiempo_interno_s"]) for x in r if x["instancia"]==i}
    g="4" if "_g04_" in i else "8"
    b.plot((0,25,50),[t[0],t[25],t[50]],"-o",color=C[g],lw=1.4,ms=4,alpha=.85)
    if t[0]>20: b.text(50.8,t[50],"semilla 3",fontsize=7.5,va="center")
b.set_xticks([0,25,50]);b.set_yscale("log");b.set_xlabel("η");b.set_ylabel("Tiempo interno (s)")
b.set_xlim(-4,62);b.set_title("η con N = 400 (una línea por instancia)",fontsize=10.5,loc="left");b.grid(alpha=.25,which="both")
from matplotlib.lines import Line2D
b.legend(handles=[Line2D([],[],color=C[k],lw=2,label=f"Grado {k}") for k in C],frameon=False,fontsize=8.5,loc="upper right")
for ax in (a,b):
    for s in("top","right"):ax.spines[s].set_visible(False)
plt.tight_layout();plt.savefig("waxman.png",dpi=200,bbox_inches="tight")

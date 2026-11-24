import csv, statistics, math, matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
plt.rcParams["font.family"]="DejaVu Sans"
R=list(csv.DictReader(open("/mnt/user-data/uploads/Capstone/Capstone-G22/experimentos/validacion/corridas.csv",encoding="utf-8")))
A=[x for x in R if x["bloque"]=="A"]; B=[x for x in R if x["bloque"]=="B"]
F=[("mulgen_g4","Mulgen g4","#1C7293"),("mulgen_g6","Mulgen g6","#0B3D5C"),("waxman_g4","Waxman g4","#F2A541"),("waxman_g6","Waxman g6","#C8741A")]
fig,ax=plt.subplots(1,3,figsize=(12.6,4.2),gridspec_kw={"width_ratios":[1,1.15,1.05]})
a=ax[0]
for f,n,c in F:
    rs=[x for x in A if x["familia"]==f]
    a.scatter([float(x["z_lp"]) for x in rs],[float(x["z_e2"]) for x in rs],s=12,color=c,alpha=.6,label=n,zorder=3)
lim=[0.9,13];a.plot(lim,lim,color="#555",lw=1,ls="--",zorder=1)
a.set_xscale("log");a.set_yscale("log");a.set_xlabel("z* del LP (HiGHS)");a.set_ylabel("z de nuestro solver")
a.set_title("Mismo resultado (400 instancias)",fontsize=10.5,loc="left");a.legend(frameon=False,fontsize=8,loc="upper left");a.grid(alpha=.25,which="both")
b=ax[1]
for i,(f,n,c) in enumerate(F):
    v=[float(x["aceleracion"]) for x in A if x["familia"]==f]
    import random; random.seed(1)
    b.scatter([i+random.uniform(-.28,.28) for _ in v],v,s=9,color=c,alpha=.55,zorder=3)
    m=statistics.median(v);b.plot([i-.35,i+.35],[m,m],color="black",lw=2,zorder=4);b.text(i,max(v)*1.25,f"med. {m:.1f}×".replace(".",","),ha="center",fontsize=8)
b.axhline(1,color="#555",lw=1,ls="--");b.set_yscale("log");b.set_xticks(range(4));b.set_xticklabels([n for _,n,_ in F],fontsize=8.5);b.set_ylim(.5,150)
b.set_ylabel("Veces más rápido (tiempo de pared)");b.set_title("Aceleración, redes de 50 nodos",fontsize=10.5,loc="left");b.grid(alpha=.25,which="both")
c=ax[2]
tl,te=[],[]
for n,rows in ((50,[x for x in A if x["familia"]=="mulgen_g4"]),(100,[x for x in B if x["nodos"]=="100"]),(200,[x for x in B if x["nodos"]=="200"])):
    tl.append(statistics.median(float(x["t_lp_s"]) for x in rows));te.append(statistics.median(float(x["t_e2_pared_s"]) for x in rows))
Ns=[50,100,200]
c.plot(Ns,tl,"-o",color="#C8741A",lw=2,label="LP (HiGHS)");c.plot(Ns,te,"-o",color="#1C7293",lw=2,label="Nuestro solver")
c.scatter([200],[tl[2]],marker="^",s=70,color="#C8741A",zorder=5);c.text(190,tl[2]*1.5,"LP no termina en 600 s",fontsize=8,ha="right")
c.set_xscale("log");c.set_yscale("log");c.set_xticks(Ns);c.set_xticklabels(["50","100","200"]);c.set_xlabel("Nodos (Mulgen grado 4)");c.set_ylabel("Tiempo (s)")
c.set_ylim(.2,2500);c.set_title("Escala: el LP deja de ser viable",fontsize=10.5,loc="left");c.legend(frameon=False,fontsize=8.5,loc="center left");c.grid(alpha=.25,which="both")
for x in ax:
    for s in("top","right"):x.spines[s].set_visible(False)
plt.tight_layout();plt.savefig("validacion.png",dpi=200,bbox_inches="tight")
print(tl,te)
allac=[float(x["aceleracion"]) for x in A];print("min",min(allac),"med",statistics.median(allac),"max",max(allac),"menor a 1:",sum(a<1 for a in allac))
print("interno med",statistics.median(float(x["t_e2_interno_s"]) for x in A))
for x in B: print(x["instancia"],x["t_lp_s"],x["t_e2_pared_s"],x["estado_lp"])

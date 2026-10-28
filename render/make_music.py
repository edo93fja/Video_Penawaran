import numpy as np, wave, sys
sr=44100; DUR=31.0; N=int(sr*(DUR+1.5))
rng=np.random.default_rng(7)
def hz(m): return 440*2**((m-69)/12)
def pluck(m,d,amp,bright=1.0):
    L=int(d*sr); t=np.arange(L)/sr; f=hz(m); y=np.zeros(L)
    for h,a,dec in [(1,1,3.0),(2,.5,5.0*bright),(3,.28,8.0*bright),(4,.14,12*bright),(5,.07,16*bright)]:
        y+=a*np.sin(2*np.pi*f*h*t)*np.exp(-dec*t)
    y*=np.minimum(1,t/0.004); return amp*y
def mallet(m,d,amp):
    L=int(d*sr); t=np.arange(L)/sr; f=hz(m)
    y=np.sin(2*np.pi*f*t)*np.exp(-5*t)+0.35*np.sin(2*np.pi*f*4*t)*np.exp(-14*t)+0.15*np.sin(2*np.pi*f*10*t)*np.exp(-30*t)
    y*=np.minimum(1,t/0.003); return amp*y
def put(buf,y,t0):
    i=int(t0*sr)
    if i>=len(buf): return
    e=min(len(buf),i+len(y)); buf[i:e]+=y[:e-i]
def kick(amp):
    L=int(0.22*sr); t=np.arange(L)/sr; fr=110*np.exp(-t*18)+45
    return amp*np.sin(2*np.pi*np.cumsum(fr)/sr)*np.exp(-t*14)
def shaker(amp):
    L=int(0.07*sr); n=rng.standard_normal(L); n=np.diff(n,prepend=0); return amp*n*np.exp(-np.arange(L)/sr*55)
def make(bpm,name,prog,mel,swing=0.0):
    beat=60/bpm; buf=np.zeros(N); bars=int((DUR+1)/(beat*4))+1
    for b in range(bars):
        chord,root=prog[b%len(prog)]; t0=b*4*beat
        # strum pattern: D . D U . U D U (8ths)
        pat=[1,0,1,1,0,1,1,1]
        for k,on in enumerate(pat):
            if not on: continue
            tt=t0+k*beat/2
            for j,m in enumerate(chord): put(buf,pluck(m,0.9,0.085 if k%2==0 else 0.06,1.0),tt+j*0.012)
        put(buf,pluck(root-12,0.6,0.16),t0); put(buf,pluck(root-12+7,0.5,0.1),t0+2*beat)
        if b>=1:
            for q in range(4): put(buf,kick(0.18 if q%2==0 else 0.0),t0+q*beat) if q%2==0 else None
            for q in range(8): put(buf,shaker(0.05 if q%2 else 0.03),t0+q*beat/2)
        if b>=2:
            for (bt,m,dur) in mel[(b-2)%len(mel)]: put(buf,mallet(m,dur,0.12),t0+bt*beat)
    fade=np.minimum(1,np.arange(N)/sr/0.6)*np.clip((DUR-np.arange(N)/sr)/2.2,0,1)
    buf*=fade; buf/=np.abs(buf).max(); buf*=0.62
    st=np.stack([buf,np.roll(buf,int(0.011*sr))],1)
    # simple room: short echo
    d=int(0.19*sr); st[d:]+=0.16*st[:-d]
    st/=np.abs(st).max()/0.7
    w=wave.open(name,"wb");w.setnchannels(2);w.setsampwidth(2);w.setframerate(sr);w.writeframes((st*32767).astype(np.int16).tobytes());w.close()
C=([60,64,67],48);G=([59,62,67],43);Am=([57,60,64],45);F=([57,60,65],41)
prog=[C,G,Am,F]
# melodi pentatonik C: bar-wise (beat,midi,dur)
mel=[[(0,76,.6),(1,79,.6),(2,81,.6),(3,79,.8)],
     [(0,79,.6),(1,76,.6),(2,74,.6),(3,76,.8)],
     [(0,72,.6),(1,76,.6),(2,79,.6),(3,76,.8)],
     [(0,77,.6),(1,76,.6),(2,74,.6),(2.5,72,1.0)]]
make(108,"render/musik-ceria.wav",prog,mel)

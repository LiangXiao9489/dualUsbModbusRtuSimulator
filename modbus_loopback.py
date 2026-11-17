import tkinter as tk
from tkinter import ttk, messagebox
import threading, random, struct, time, queue
import serial
from serial.tools import list_ports

def crc(b):
    c=65535
    for x in b:
        c^=x
        for _ in range(8): c=(c>>1)^40961 if c&1 else c>>1
    return c
def frame(b): return b+struct.pack('<H',crc(b))
def ok(b): return len(b)>3 and crc(b[:-2])==struct.unpack('<H',b[-2:])[0]
def text(b): return ' '.join('%02X'%x for x in b)
def readf(p, stop, request=False):
    b=bytearray()
    while not stop.is_set():
        x=p.read(1)
        if not x: return bytes(b) if b else None
        b+=x; n=None
        if len(b)>=2 and b[1]&128: n=5
        elif len(b)>=3:
            f=b[1]; n=8 if f in (1,2,3,4,5,6,15) and (f in (5,6,15) or request) else (5+b[2])
            if f==16: n=(9+b[6]) if request and len(b)>6 else 8
        if n and len(b)>=n:return bytes(b[:n])

class App(tk.Tk):
 def __init__(self):
  super().__init__(); self.title('双 USB-RS485 Modbus RTU 回环模拟器'); self.geometry('950x650'); self.stop=threading.Event(); self.ps=[]; self.log_queue=queue.Queue(); self.make(); self.ports(); self.after(100,self.flush); self.protocol('WM_DELETE_WINDOW',self.close)
 def make(self):
  self.v={k:tk.StringVar(value=x) for k,x in {'m':'','s':'','baud':'9600','parity':'N','data':'8','stop':'1','unit':'1','interval':'1','cycles':'0'}.items()}
  g=ttk.LabelFrame(self,text='串口及轮询参数');g.pack(fill='x',padx=8,pady=6)
  fs=[('主站串口','m'),('从站串口','s'),('波特率','baud'),('校验','parity'),('数据位','data'),('停止位','stop'),('从站地址','unit'),('间隔(秒)','interval'),('循环次数(0=无限)','cycles')]
  for i,(t,k) in enumerate(fs):
   ttk.Label(g,text=t).grid(row=i//5*2,column=i%5*2,sticky='w'); w=ttk.Combobox(g,textvariable=self.v[k],width=9,state='readonly') if k in ('m','s','parity') else ttk.Entry(g,textvariable=self.v[k],width=9); w.grid(row=i//5*2+1,column=i%5*2)
   if k=='parity':w['values']=('N','E','O')
   setattr(self,k+'_widget',w)
  ttk.Button(g,text='刷新串口',command=self.ports).grid(row=1,column=9);ttk.Button(g,text='开始',command=self.start).grid(row=3,column=8);ttk.Button(g,text='停止',command=self.stoprun).grid(row=3,column=9)
  p=ttk.LabelFrame(self,text='一键配置从机随机点表');p.pack(fill='x',padx=8,pady=4);self.n={k:tk.IntVar(value=100) for k in ('线圈','离散输入','输入寄存器','保持寄存器')}
  for i,k in enumerate(self.n):ttk.Label(p,text=k+'数量').grid(row=0,column=i*2);ttk.Entry(p,textvariable=self.n[k],width=8).grid(row=0,column=i*2+1)
  ttk.Button(p,text='生成随机点表',command=self.points).grid(row=0,column=8);self.status=ttk.Label(p,text='未生成');self.status.grid(row=0,column=9)
  split=ttk.PanedWindow(self,orient='horizontal');split.pack(fill='both',expand=True,padx=8,pady=6)
  left=ttk.LabelFrame(split,text='实际从站点表');right=ttk.LabelFrame(split,text='运行 Log');split.add(left,weight=1);split.add(right,weight=2)
  self.tables={}; tabs=ttk.Notebook(left);tabs.pack(fill='both',expand=True)
  for title,fn in (('线圈',1),('离散输入',2),('输入寄存器',4),('保持寄存器',3)):
   tab=ttk.Frame(tabs);tabs.add(tab,text=title);tree=ttk.Treeview(tab,columns=('address','value'),show='headings');tree.heading('address',text='地址');tree.heading('value',text='值');tree.column('address',width=70,anchor='center');tree.column('value',width=90,anchor='center');tree.pack(side='left',fill='both',expand=True);scroll=ttk.Scrollbar(tab,orient='vertical',command=tree.yview);scroll.pack(side='right',fill='y');tree.configure(yscrollcommand=scroll.set);self.tables[fn]=tree
  self.log=tk.Text(right,state='disabled');self.log.pack(fill='both',expand=True)
 def ports(self):
  a=[x.device for x in list_ports.comports()];self.m_widget['values']=self.s_widget['values']=a
  if a and not self.v['m'].get():self.v['m'].set(a[0])
  if len(a)>1 and not self.v['s'].get():self.v['s'].set(a[1])
 def points(self):
  self.status.config(text='已生成 '+time.strftime('%H:%M:%S'));counts={1:self.n['线圈'].get(),2:self.n['离散输入'].get(),3:self.n['保持寄存器'].get(),4:self.n['输入寄存器'].get()};self.data={f:{i:random.randint(0,1 if f<3 else 65535) for i in range(counts[f])} for f in range(1,5)};self.refresh_points()
 def refresh_points(self):
  for f,tree in self.tables.items():
   tree.delete(*tree.get_children())
   for address,value in self.data.get(f,{}).items(): tree.insert('', 'end', values=(address,value))
 def put(self,s): self.log_queue.put(s)
 def start(self):
  if self.ps:return
  try:
   kw=dict(baudrate=int(self.v['baud'].get()),bytesize=int(self.v['data'].get()),parity=self.v['parity'].get(),stopbits=float(self.v['stop'].get()),timeout=.05);self.unit=int(self.v['unit'].get());self.data=getattr(self,'data', {f:{i:0 for i in range(100)} for f in range(1,5)});self.ps=[serial.Serial(self.v['m'].get(),**kw),serial.Serial(self.v['s'].get(),**kw)];self.stop.clear();self.put('111已开始');threading.Thread(target=self.slave_loop,daemon=True).start();threading.Thread(target=self.master_loop,daemon=True).start()
  except Exception as e:self.put('启动失败: '+str(e));self.stoprun()
 def slave_loop(self):
  try:
   while not self.stop.is_set():
    q=readf(self.ps[1],self.stop,True)
    if q:self.put('[slave 接收到 master 发送 '+text(q)+']');r=self.reply(q)
    else:r=None
    if r:self.ps[1].write(r);self.put('[slave 返回 '+text(r)+' 给 master]')
  except Exception as e:self.put('[slave 线程异常: '+str(e)+']')
 def reply(self,q):
  if len(q)<8 or q[0]!=self.unit or not ok(q):return None
  f=q[1];a,n=struct.unpack('>HH',q[2:6]);d=self.data.get(f)
  if f in (1,2,3,4) and d is not None and all(x in d for x in range(a,a+n)):
   if f<3:
    z=sum(d[a+i]<<i for i in range(n));return frame(bytes((self.unit,f,(n+7)//8))+z.to_bytes((n+7)//8,'little'))
   z=b''.join(struct.pack('>H',d[a+i]) for i in range(n));return frame(bytes((self.unit,f,len(z)))+z)
  if f in (5,6) and a in self.data[1 if f==5 else 3]: self.data[1 if f==5 else 3][a]=q[5]&1 if f==5 else struct.unpack('>H',q[4:6])[0];self.after(0,self.refresh_points);return q
  return frame(bytes((self.unit,f|128,2)))
 def master_loop(self):
  try:
   self.put('[master 工作线程已启动]')
   fs=[1,2,3,4,5,6];limit=int(self.v['cycles'].get());i=0
   while not self.stop.is_set() and (not limit or i<limit):
    f=random.choice(fs);a=random.randrange(0,30);n=random.randint(1,4);v=random.randint(0,1 if f==5 else 65535)
    q=frame(struct.pack('>BBHH',self.unit,f,a,n if f<5 else v));self.ps[0].write(q);self.put('[master 发送 '+text(q)+' 到 slave]');r=readf(self.ps[0],self.stop)
    if r:self.put('[master 接收到 slave 返回 '+text(r)+']'+(' [CRC OK]' if ok(r) else ' [CRC ERROR]'))
    i+=1;self.stop.wait(float(self.v['interval'].get()))
   if limit:self.put('--- 完成 %d 次 ---'%i)
  except Exception as e:self.put('[master 线程异常: '+str(e)+']')
 def stoprun(self):
  self.stop.set()
  for p in self.ps:
   try:p.close()
   except:pass
  self.ps=[]
 def flush(self):
  while True:
   try:s=self.log_queue.get_nowait()
   except queue.Empty:break
   self.log.config(state='normal');self.log.insert('end',time.strftime('%H:%M:%S ')+s+'\n');self.log.see('end');self.log.config(state='disabled')
  self.after(100,self.flush)
 def close(self):self.stoprun();self.destroy()
if __name__=='__main__':App().mainloop()

import { useEffect, useMemo, useState } from 'react';
import {
  Activity, ArrowDownToLine, ArrowUpFromLine, Bell, BookOpen, Building2,
  Check, ChevronDown, ChevronLeft, ChevronRight, CircleHelp, Clock3,
  Database, Download, FileCheck2, GraduationCap, LayoutDashboard, Menu,
  MoreHorizontal, Plus, Search, Settings, ShieldCheck, SlidersHorizontal,
  Users, X, Zap,
} from 'lucide-react';

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000';
type Student = {
  id: number; matric_number: string; first_name: string; last_name: string;
  email: string; department: string; level: string; status: string;
};
type Backup = { filename: string; size_bytes: number; modified_at: string };
type Dashboard = {
  total_students: number; active_students: number; departments: number;
  available_backups: number; recent_activity: {id:number;action:string;details:string;created_at:string}[];
  students_by_department: {name:string;count:number}[];
};

async function request(path: string, options?: RequestInit) {
  const response = await fetch(API + path, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...(options?.headers || {}) },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || 'The request could not be completed.');
  }
  return response.json();
}
const initials = (s: Student) => (s.first_name[0] + s.last_name[0]).toUpperCase();
const dateLabel = (value: string) => new Date(value).toLocaleString([], {month:'short',day:'numeric',hour:'2-digit',minute:'2-digit'});
const bytes = (n: number) => n < 1024 ? n + ' B' : (n/1024).toFixed(1) + ' KB';

export default function App() {
  const [page, setPage] = useState('Overview');
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  const [students, setStudents] = useState<Student[]>([]);
  const [backups, setBackups] = useState<Backup[]>([]);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [modal, setModal] = useState(false);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({matric_number:'',first_name:'',last_name:'',email:'',department:'Computer Engineering',level:'300',status:'Active'});

  async function refresh() {
    setLoading(true); setError('');
    try {
      const [d,s,b] = await Promise.all([
        request('/api/dashboard'), request('/api/students'), request('/api/backups'),
      ]);
      setDashboard(d); setStudents(s); setBackups(b);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not connect to the API.');
    } finally { setLoading(false); }
  }
  useEffect(() => { void refresh(); }, []);
  useEffect(() => {
    if (!notice) return;
    const timer = window.setTimeout(() => setNotice(''), 3500);
    return () => window.clearTimeout(timer);
  }, [notice]);

  const filtered = useMemo(() => students.filter(s =>
    [s.first_name,s.last_name,s.matric_number,s.department].join(' ').toLowerCase().includes(search.toLowerCase())
  ), [students,search]);

  async function addStudent(e: React.FormEvent) {
    e.preventDefault(); setSaving(true);
    try {
      await request('/api/students', {method:'POST',body:JSON.stringify(form)});
      setModal(false); setForm({matric_number:'',first_name:'',last_name:'',email:'',department:'Computer Engineering',level:'300',status:'Active'});
      setNotice('Student record added successfully.'); await refresh();
    } catch (e) { setNotice(e instanceof Error ? e.message : 'Could not save student.'); }
    finally { setSaving(false); }
  }
  async function createBackup() {
    try { const result = await request('/api/backups',{method:'POST'}); setNotice('Backup created · ' + result.filename); await refresh(); }
    catch(e) { setNotice(e instanceof Error ? e.message : 'Backup failed.'); }
  }
  async function restoreBackup(filename: string) {
    if (!window.confirm('Restore this database snapshot? The current database will first be preserved as a safety copy.')) return;
    try { await request('/api/backups/'+encodeURIComponent(filename)+'/restore',{method:'POST'}); setNotice('Database restored and integrity check passed.'); await refresh(); }
    catch(e) { setNotice(e instanceof Error ? e.message : 'Restore failed.'); }
  }
  const nav = [
    {label:'Overview',icon:LayoutDashboard},
    {label:'Students',icon:Users},
    {label:'Departments',icon:Building2},
    {label:'Results',icon:BookOpen},
    {label:'Backup & Recovery',icon:Database},
    {label:'Activity Log',icon:Activity},
  ];
  return <div className="app-shell">
    <aside className="sidebar">
      <div className="brand"><div className="brand-mark"><GraduationCap size={21}/></div><span>campus<span className="brand-light">book</span></span></div>
      <div className="workspace"><div className="workspace-avatar">RS</div><div><b>Rivers State University</b><small>Administration</small></div><ChevronDown size={15}/></div>
      <div className="nav-label">WORKSPACE</div>
      <nav>{nav.map(item => <button key={item.label} className={'nav-item '+(page===item.label?'active':'')} onClick={()=>setPage(item.label)}><item.icon size={18}/><span>{item.label}</span>{item.label==='Backup & Recovery' && <i className="nav-dot"/>}</button>)}</nav>
      <div className="sidebar-bottom">
        <button className="nav-item"><Settings size={18}/>Settings</button>
        <button className="nav-item"><CircleHelp size={18}/>Help & support</button>
        <div className="profile"><div className="profile-avatar">CC</div><div><b>Campus Admin</b><small>Administrator</small></div><MoreHorizontal size={18}/></div>
      </div>
    </aside>
    <main className="main">
      <header className="topbar"><div className="breadcrumb"><span>Workspace</span><ChevronRight size={14}/><b>{page}</b></div><div className="top-actions"><div className="system-status"><i/>System operational</div><button className="icon-button"><Bell size={18}/><em/></button><div className="top-avatar">CC</div></div></header>
      <div className="content">
        {error && <div className="error-banner"><Database size={17}/><div><b>Can't reach the CampusBook API</b><span>{error} Start the FastAPI server on port 8000, then refresh.</span></div><button onClick={refresh}>Retry</button></div>}
        {notice && <div className="toast"><Check size={16}/>{notice}<button onClick={()=>setNotice('')}><X size={15}/></button></div>}
        {page==='Overview' && <>
          <div className="page-heading"><div><div className="eyebrow">TUESDAY, 17 NOVEMBER 2026</div><h1>Good morning, Admin <span>✦</span></h1><p>Here’s what’s happening across your institution today.</p></div><button className="primary-button" onClick={()=>setModal(true)}><Plus size={17}/> Add student</button></div>
          <section className="stats-grid">
            <Stat icon={Users} label="Total students" value={dashboard?.total_students ?? '—'} note="Registered student records" tone="blue"/>
            <Stat icon={ShieldCheck} label="Active students" value={dashboard?.active_students ?? '—'} note="Currently active records" tone="green"/>
            <Stat icon={Building2} label="Departments" value={dashboard?.departments ?? '—'} note="Academic departments" tone="violet"/>
            <Stat icon={Database} label="Available backups" value={dashboard?.available_backups ?? '—'} note="Verified database snapshots" tone="amber"/>
          </section>
          <div className="dashboard-grid">
            <section className="panel students-panel"><div className="panel-head"><div><h2>Recent students</h2><p>Latest records added to CampusBook</p></div><button className="text-button" onClick={()=>setPage('Students')}>View all <ChevronRight size={15}/></button></div><StudentTable rows={students.slice(0,5)} /></section>
            <section className="panel activity-panel"><div className="panel-head"><div><h2>Recent activity</h2><p>Latest system events</p></div><button className="more-button"><MoreHorizontal size={19}/></button></div>
              {dashboard?.recent_activity?.length ? <div className="activity-list">{dashboard.recent_activity.map(a=><div className="activity-row" key={a.id}><div className="activity-icon"><Activity size={15}/></div><div><b>{a.action}</b><span>{a.details}</span><small>{dateLabel(a.created_at)}</small></div></div>)}</div> : <Empty icon={Activity} title="No activity yet" detail="System events will appear here as you work."/>}
            </section>
          </div>
          <section className="panel backup-banner"><div className="backup-symbol"><Database size={22}/></div><div className="backup-copy"><h2>Your data, protected.</h2><p>Create a database snapshot before making major changes. You can restore a verified backup if records are accidentally lost.</p></div><button className="secondary-button" onClick={()=>setPage('Backup & Recovery')}>Manage backups <ArrowUpFromLine size={16}/></button></section>
        </>}
        {page==='Students' && <><div className="page-heading"><div><div className="eyebrow">RECORDS MANAGEMENT</div><h1>Students</h1><p>Manage student profiles and academic records.</p></div><button className="primary-button" onClick={()=>setModal(true)}><Plus size={17}/> Add student</button></div><section className="panel table-panel"><div className="table-toolbar"><div><h2>All students <span className="count-pill">{students.length}</span></h2><p>Search and manage registered students</p></div><div className="table-tools"><div className="search-box"><Search size={16}/><input placeholder="Search students..." value={search} onChange={e=>setSearch(e.target.value)}/></div><button className="filter-button"><SlidersHorizontal size={16}/> Filter</button></div></div><StudentTable rows={filtered} /></section></>}
        {page==='Backup & Recovery' && <><div className="page-heading"><div><div className="eyebrow">DATA PROTECTION</div><h1>Backup & recovery</h1><p>Protect your records with verified database snapshots.</p></div><button className="primary-button" onClick={createBackup}><Plus size={17}/> Create backup</button></div>
          <div className="recovery-callout"><div className="callout-icon"><ShieldCheck size={21}/></div><div><b>Your database is ready for protection</b><p>CampusBook uses SQLite's online backup API and checks database integrity before a snapshot is accepted.</p></div><span className="secure-pill"><i/> Integrity checks enabled</span></div>
          <section className="panel table-panel"><div className="table-toolbar"><div><h2>Backup history <span className="count-pill">{backups.length}</span></h2><p>Snapshots stored on the application server</p></div><button className="filter-button" onClick={refresh}><Activity size={16}/> Refresh</button></div>
            {backups.length ? <div className="backup-list">{backups.map(b=><div className="backup-row" key={b.filename}><div className="file-icon"><Database size={19}/></div><div className="backup-file"><b>{b.filename}</b><span>{dateLabel(b.modified_at)} · {bytes(b.size_bytes)}</span></div><span className="verified"><Check size={14}/> Available</span><button className="restore-button" onClick={()=>restoreBackup(b.filename)}><ArrowDownToLine size={15}/> Restore</button></div>)}</div> : <Empty icon={Database} title="No backups created yet" detail="Create your first snapshot to protect the student database."/>}
          </section>
          <div className="recovery-note"><Zap size={17}/><div><b>Recovery safety</b><span>Before restoring a snapshot, CampusBook preserves the current database as a separate safety copy.</span></div></div>
        </>}
        {page==='Departments' && <SimplePage title="Departments" desc="Academic departments and their registered student counts." icon={Building2} rows={dashboard?.students_by_department?.map(d=>({name:d.name,detail:d.count+' students'}))||[]}/>}
        {page==='Results' && <SimplePage title="Results management" desc="Student course results will be managed from this module." icon={BookOpen} rows={[]}/>}
        {page==='Activity Log' && <SimplePage title="Activity log" desc="A chronological record of important system actions." icon={Activity} rows={dashboard?.recent_activity?.map(a=>({name:a.action,detail:a.details+' · '+dateLabel(a.created_at)}))||[]}/>}
        <footer className="footer"><span>© 2026 CampusBook · Academic project</span><span>Built for reliable student records <span className="footer-heart">♥</span></span></footer>
      </div>
    </main>
    {modal && <div className="modal-backdrop" onClick={()=>setModal(false)}><form className="modal" onSubmit={addStudent} onClick={e=>e.stopPropagation()}><div className="modal-head"><div><div className="eyebrow">STUDENT RECORD</div><h2>Add a student</h2><p>Enter the student's information below.</p></div><button type="button" className="icon-button" onClick={()=>setModal(false)}><X size={18}/></button></div><div className="form-grid">
      <label>First name<input required value={form.first_name} onChange={e=>setForm({...form,first_name:e.target.value})}/></label>
      <label>Last name<input required value={form.last_name} onChange={e=>setForm({...form,last_name:e.target.value})}/></label>
      <label className="full">Matriculation number<input required value={form.matric_number} onChange={e=>setForm({...form,matric_number:e.target.value})} placeholder="e.g. RSU/2024/CPE/001"/></label>
      <label className="full">Email address<input type="email" required value={form.email} onChange={e=>setForm({...form,email:e.target.value})}/></label>
      <label>Department<select value={form.department} onChange={e=>setForm({...form,department:e.target.value})}><option>Computer Engineering</option><option>Computer Science</option><option>Electrical Engineering</option><option>Accountancy</option></select></label>
      <label>Level<select value={form.level} onChange={e=>setForm({...form,level:e.target.value})}>{['100','200','300','400','500'].map(v=><option key={v}>{v}</option>)}</select></label>
    </div><div className="modal-actions"><button type="button" className="secondary-button" onClick={()=>setModal(false)}>Cancel</button><button className="primary-button" disabled={saving}>{saving?'Saving…':'Save student'}</button></div></form></div>}
  </div>;
}

function Stat({icon:Icon,label,value,note,tone}:{icon:any;label:string;value:any;note:string;tone:string}) {
  return <div className="stat-card"><div className={'stat-icon '+tone}><Icon size={19}/></div><div className="stat-label">{label}</div><div className="stat-value">{value}</div><div className="stat-note">{note}</div></div>;
}
function StudentTable({rows}:{rows:Student[]}) {
  return <div className="table-wrap"><table><thead><tr><th>STUDENT</th><th>MATRIC NUMBER</th><th>DEPARTMENT</th><th>LEVEL</th><th>STATUS</th></tr></thead><tbody>{rows.map(s=><tr key={s.id}><td><div className="student-cell"><div className="student-avatar">{initials(s)}</div><div><b>{s.first_name} {s.last_name}</b><span>{s.email}</span></div></div></td><td className="mono">{s.matric_number}</td><td>{s.department}</td><td>{s.level} Level</td><td><span className={'status '+(s.status==='Active'?'status-active':'status-inactive')}><i/>{s.status}</span></td></tr>)}</tbody></table>{!rows.length&&<Empty icon={Users} title="No student records" detail="Add a student to get started."/>}</div>;
}
function Empty({icon:Icon,title,detail}:{icon:any;title:string;detail:string}) {
  return <div className="empty-state"><div><Icon size={22}/></div><b>{title}</b><span>{detail}</span></div>;
}
function SimplePage({title,desc,icon:Icon,rows}:{title:string;desc:string;icon:any;rows:{name:string;detail:string}[]}) {
  return <><div className="page-heading"><div><div className="eyebrow">CAMPUSBOOK MODULE</div><h1>{title}</h1><p>{desc}</p></div></div><section className="panel simple-panel">{rows.length?rows.map((r,i)=><div className="simple-row" key={i}><div className="simple-icon"><Icon size={18}/></div><b>{r.name}</b><span>{r.detail}</span></div>):<Empty icon={Icon} title="Nothing to show yet" detail="This module will be expanded in the next development stage."/>}</section></>;
}

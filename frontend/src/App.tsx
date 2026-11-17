import { useEffect, useMemo, useState } from 'react';
import type { FormEvent, ReactNode } from 'react';
import {
  Activity, ArrowDownToLine, BookOpen, Building2, Check, Menu,
  ChevronRight, Database, GraduationCap, LayoutDashboard,
  Plus, Search, ShieldCheck, Users, X, Pencil, Trash2,
  RefreshCw,
} from 'lucide-react';

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000';
type Student = {
  id:number; matric_number:string; first_name:string; last_name:string;
  department:string; level:string; status:string; created_at:string;
};
type Department = {id:number;name:string;code:string;student_count:number};
type Result = {id:number;student_id:number;course_code:string;course_title:string;score:number;semester:string;matric_number:string;first_name:string;last_name:string};
type Backup = {filename:string;size_bytes:number;modified_at:string};
type ActivityItem = {id:number;action:string;details:string;created_at:string};
type Dashboard = {total_students:number;active_students:number;departments:number;available_backups:number;recent_activity:ActivityItem[];students_by_department:{name:string;count:number}[]};
type StudentForm = Omit<Student,'id'|'created_at'>;

class ApiError extends Error {
  constructor(message:string,readonly status:number){super(message);this.name='ApiError';}
}
async function request<T=any>(path:string, options?:RequestInit):Promise<T> {
  const response = await fetch(API+path,{...options,headers:{'Content-Type':'application/json',...(options?.headers||{})}});
  if(!response.ok){
    const body=await response.json().catch(()=>({}));
    throw new ApiError(body.detail||(response.status===502||response.status===503||response.status===504?'CampusBook is starting up.':'The request could not be completed.'),response.status);
  }
  if(response.status===204)return undefined as T;
  return response.json();
}
const wait=(ms:number)=>new Promise(resolve=>window.setTimeout(resolve,ms));
async function requestWithRetry<T>(path:string,attempts=8):Promise<T>{
  let lastError:unknown;
  for(let attempt=0;attempt<attempts;attempt++){
    try{return await request<T>(path);}
    catch(error){
      lastError=error;
      const transient=(error instanceof ApiError&&[502,503,504].includes(error.status))||error instanceof TypeError;
      if(!transient||attempt===attempts-1)throw error;
      await wait(Math.min(2000*(2**attempt),12000));
    }
  }
  throw lastError instanceof Error?lastError:new Error('Could not connect to CampusBook.');
}
const emptyStudent:StudentForm={matric_number:'',first_name:'',last_name:'',department:'Computer Engineering',level:'300',status:'Active'};
const dateLabel=(v:string)=>new Date(v).toLocaleString([],{month:'short',day:'numeric',year:'numeric',hour:'2-digit',minute:'2-digit'});
const bytes=(n:number)=>n<1024?n+' B':(n/1024).toFixed(1)+' KB';
const initials=(s:Student)=>(s.first_name[0]+s.last_name[0]).toUpperCase();

export default function App(){
  const [page,setPage]=useState('Overview');
  const [mobileNavOpen,setMobileNavOpen]=useState(false);
  const [dashboard,setDashboard]=useState<Dashboard|null>(null);
  const [students,setStudents]=useState<Student[]>([]);
  const [departments,setDepartments]=useState<Department[]>([]);
  const [results,setResults]=useState<Result[]>([]);
  const [backups,setBackups]=useState<Backup[]>([]);
  const [activity,setActivity]=useState<ActivityItem[]>([]);
  const [search,setSearch]=useState('');
  const [studentStatus,setStudentStatus]=useState('All');
  const [studentDepartment,setStudentDepartment]=useState('All');
  const [loading,setLoading]=useState(true);
  const [error,setError]=useState('');
  const [notice,setNotice]=useState('');
  const [studentModal,setStudentModal]=useState(false);
  const [editingStudent,setEditingStudent]=useState<Student|null>(null);
  const [studentForm,setStudentForm]=useState<StudentForm>(emptyStudent);
  const [resultModal,setResultModal]=useState(false);
  const [resultForm,setResultForm]=useState({student_id:'',course_code:'',course_title:'',score:'',semester:'First Semester 2026/2027'});
  const [departmentModal,setDepartmentModal]=useState(false);
  const [departmentForm,setDepartmentForm]=useState({name:'',code:''});
  const [saving,setSaving]=useState(false);

  async function refresh(){
    setLoading(true);setError('');
    try{
      const [d,s,de,r,b,a]=await Promise.all([
        requestWithRetry<Dashboard>('/api/dashboard'),requestWithRetry<Student[]>('/api/students'),
        requestWithRetry<Department[]>('/api/departments'),requestWithRetry<Result[]>('/api/results'),
        requestWithRetry<Backup[]>('/api/backups'),requestWithRetry<ActivityItem[]>('/api/activity'),
      ]);
      setDashboard(d);setStudents(s);setDepartments(de);setResults(r);setBackups(b);setActivity(a);
    }catch(e){setError(e instanceof Error?e.message:'Could not connect to the API.');}
    finally{setLoading(false);}
  }
  useEffect(()=>{void refresh();},[]);
  useEffect(()=>{if(!notice)return;const t=window.setTimeout(()=>setNotice(''),4000);return()=>window.clearTimeout(t);},[notice]);

  const filteredStudents=useMemo(()=>students.filter(s=>{
    const matchesSearch=[s.first_name,s.last_name,s.matric_number,s.department].join(' ').toLowerCase().includes(search.toLowerCase());
    const matchesStatus=studentStatus==='All'||s.status===studentStatus;
    const matchesDepartment=studentDepartment==='All'||s.department===studentDepartment;
    return matchesSearch&&matchesStatus&&matchesDepartment;
  }),[students,search,studentStatus,studentDepartment]);

  function openCreateStudent(){setEditingStudent(null);setStudentForm(emptyStudent);setStudentModal(true);}
  function openEditStudent(s:Student){setEditingStudent(s);setStudentForm({matric_number:s.matric_number,first_name:s.first_name,last_name:s.last_name,department:s.department,level:s.level,status:s.status});setStudentModal(true);}
  async function saveStudent(e:FormEvent){
    e.preventDefault();setSaving(true);
    try{
      await request(editingStudent?'/api/students/'+editingStudent.id:'/api/students',{method:editingStudent?'PUT':'POST',body:JSON.stringify(studentForm)});
      setStudentModal(false);setNotice(editingStudent?'Student record updated.':'Student record created.');await refresh();
    }catch(e){setNotice(e instanceof Error?e.message:'Could not save student.');}finally{setSaving(false);}
  }
  async function deleteStudent(s:Student){
    if(!window.confirm('Delete '+s.first_name+' '+s.last_name+'? Associated results will also be deleted.'))return;
    try{await request('/api/students/'+s.id,{method:'DELETE'});setNotice('Student deleted.');await refresh();}
    catch(e){setNotice(e instanceof Error?e.message:'Could not delete student.');}
  }
  async function createBackup(){
    try{const b=await request<{filename:string}>('/api/backups',{method:'POST'});setNotice('Backup created: '+b.filename);await refresh();}
    catch(e){setNotice(e instanceof Error?e.message:'Backup failed.');}
  }
  async function restoreBackup(filename:string){
    if(!window.confirm('Restore this snapshot? The current database will first be saved as a safety copy.'))return;
    try{await request('/api/backups/'+encodeURIComponent(filename)+'/restore',{method:'POST'});setNotice('Database restored successfully.');await refresh();}
    catch(e){setNotice(e instanceof Error?e.message:'Restore failed.');}
  }
  async function saveDepartment(e:FormEvent){
    e.preventDefault();setSaving(true);
    try{await request('/api/departments',{method:'POST',body:JSON.stringify(departmentForm)});setDepartmentModal(false);setDepartmentForm({name:'',code:''});setNotice('Department added.');await refresh();}
    catch(e){setNotice(e instanceof Error?e.message:'Could not add department.');}finally{setSaving(false);}
  }
  async function saveResult(e:FormEvent){
    e.preventDefault();setSaving(true);
    try{await request('/api/results',{method:'POST',body:JSON.stringify({...resultForm,student_id:Number(resultForm.student_id),score:Number(resultForm.score)})});setResultModal(false);setResultForm({student_id:'',course_code:'',course_title:'',score:'',semester:'First Semester 2026/2027'});setNotice('Result recorded.');await refresh();}
    catch(e){setNotice(e instanceof Error?e.message:'Could not save result.');}finally{setSaving(false);}
  }
  async function deleteResult(r:Result){
    if(!window.confirm('Delete the result for '+r.course_code+'?'))return;
    try{await request('/api/results/'+r.id,{method:'DELETE'});setNotice('Result deleted.');await refresh();}
    catch(e){setNotice(e instanceof Error?e.message:'Could not delete result.');}
  }

  const nav=[{label:'Overview',icon:LayoutDashboard},{label:'Students',icon:Users},{label:'Departments',icon:Building2},{label:'Results',icon:BookOpen},{label:'Backup & Recovery',icon:Database},{label:'Activity Log',icon:Activity}];
  return <div className="app-shell">
    <aside className={'sidebar '+(mobileNavOpen?'mobile-open':'')}>
      <div className="mobile-brand"><div className="brand-mark"><GraduationCap size={21}/></div><span>campus<span className="brand-light">book</span></span></div>
      <div className="brand"><div className="brand-mark"><GraduationCap size={21}/></div><span>campus<span className="brand-light">book</span></span></div>
      <div className="workspace"><div className="workspace-avatar">RS</div><div><b>Rivers State University</b><small>Academic records</small></div></div>
      <div className="nav-label">WORKSPACE</div>
      <nav>{nav.map(item=><button key={item.label} className={'nav-item '+(page===item.label?'active':'')} onClick={()=>{setPage(item.label);setMobileNavOpen(false);}}><item.icon size={18}/><span>{item.label}</span>{item.label==='Backup & Recovery'&&<i className="nav-dot"/>}</button>)}</nav>
      <div className="sidebar-bottom"><div className="profile"><div className="profile-avatar">CA</div><div><b>Campus Admin</b><small>Demo administrator</small></div></div></div>
    </aside>
    <main className="main">
      <header className="topbar"><button className="mobile-menu-button" aria-label="Open navigation" onClick={()=>setMobileNavOpen(v=>!v)}><Menu size={20}/></button><div className="breadcrumb"><span>Workspace</span><ChevronRight size={14}/><b>{page}</b></div><div className="top-actions"><div className="system-status"><i/>System operational</div><div className="top-avatar">CA</div></div></header>
      <div className="content">
        {loading&&!dashboard&&!error&&<div className="loading-banner"><RefreshCw size={17} className="spin"/><div><b>Connecting to CampusBook</b><span>The server may be waking up. We'll reconnect automatically; this can take up to a minute.</span></div></div>}
        {error&&<div className="error-banner"><Database size={17}/><div><b>CampusBook is temporarily unavailable</b><span>{error} We tried reconnecting automatically. Please try again.</span></div><button onClick={()=>void refresh()}>Retry</button></div>}
        {notice&&<div className="toast"><Check size={16}/>{notice}<button onClick={()=>setNotice('')}><X size={15}/></button></div>}
        {page==='Overview'&&<>
          <PageHeading eyebrow="INSTITUTION OVERVIEW" title="Good morning, Admin" description="Here’s what’s happening across your institution today." action={<button className="primary-button" onClick={openCreateStudent}><Plus size={17}/> Add student</button>}/>
          <section className="stats-grid">
            <Stat icon={Users} label="Total students" value={dashboard?.total_students??'—'} note="Registered student records" tone="blue"/>
            <Stat icon={ShieldCheck} label="Active students" value={dashboard?.active_students??'—'} note="Currently active records" tone="green"/>
            <Stat icon={Building2} label="Departments" value={dashboard?.departments??'—'} note="Academic departments" tone="violet"/>
            <Stat icon={Database} label="Available backups" value={dashboard?.available_backups??'—'} note="Database snapshots" tone="amber"/>
          </section>
          <div className="dashboard-grid">
            <section className="panel students-panel"><PanelHead title="Recent students" subtitle="Latest records added to CampusBook" action={<button className="text-button" onClick={()=>setPage('Students')}>View all <ChevronRight size={15}/></button>}/><StudentTable rows={students.slice(0,5)} onEdit={openEditStudent} onDelete={deleteStudent}/></section>
            <section className="panel activity-panel"><PanelHead title="Recent activity" subtitle="Latest system events"/><ActivityList rows={activity.slice(0,6)}/></section>
          </div>
          <section className="panel backup-banner"><div className="backup-symbol"><Database size={22}/></div><div className="backup-copy"><h2>Your data, protected.</h2><p>Create a database snapshot before major changes. Restore a verified backup if records are accidentally lost.</p></div><button className="secondary-button" onClick={()=>setPage('Backup & Recovery')}>Manage backups <ChevronRight size={16}/></button></section>
        </>}
        {page==='Students'&&<>
          <PageHeading eyebrow="RECORDS MANAGEMENT" title="Students" description="Manage student profiles and academic records." action={<button className="primary-button" onClick={openCreateStudent}><Plus size={17}/> Add student</button>}/>
          <section className="panel table-panel"><div className="table-toolbar"><div><h2>All students <span className="count-pill">{students.length}</span></h2><p>Search, edit and manage registered students</p></div><div className="table-tools"><div className="search-box"><Search size={16}/><input placeholder="Search name or matric number" value={search} onChange={e=>setSearch(e.target.value)}/></div><select className="filter-select" aria-label="Filter by status" value={studentStatus} onChange={e=>setStudentStatus(e.target.value)}><option value="All">All statuses</option><option value="Active">Active</option><option value="Inactive">Inactive</option></select><select className="filter-select" aria-label="Filter by department" value={studentDepartment} onChange={e=>setStudentDepartment(e.target.value)}><option value="All">All departments</option>{departments.map(d=><option key={d.id} value={d.name}>{d.name}</option>)}</select><button className="filter-button" onClick={()=>{setSearch('');setStudentStatus('All');setStudentDepartment('All');}}><X size={15}/> Reset</button></div></div><div className="results-caption">Showing <b>{filteredStudents.length}</b> of <b>{students.length}</b> student records</div><StudentTable rows={filteredStudents} onEdit={openEditStudent} onDelete={deleteStudent}/></section>
        </>}
        {page==='Departments'&&<>
          <PageHeading eyebrow="ACADEMIC STRUCTURE" title="Departments" description="Manage academic departments and view their student counts." action={<button className="primary-button" onClick={()=>setDepartmentModal(true)}><Plus size={17}/> Add department</button>}/>
          <section className="panel table-panel"><PanelHead title="All departments" subtitle={departments.length+' registered departments'}/><div className="simple-panel">{departments.map(d=><div className="simple-row" key={d.id}><div className="simple-icon"><Building2 size={18}/></div><b>{d.name}</b><span className="dept-code">{d.code}</span><span>{d.student_count} students</span></div>)}{!departments.length&&<Empty icon={Building2} title="No departments" detail="Add the first academic department."/>}</div></section>
        </>}
        {page==='Results'&&<>
          <PageHeading eyebrow="ACADEMIC PERFORMANCE" title="Results management" description="Record and review course results for registered students." action={<button className="primary-button" onClick={()=>setResultModal(true)} disabled={!students.length}><Plus size={17}/> Record result</button>}/>
          <section className="panel table-panel"><PanelHead title="Recorded results" subtitle={results.length+' course results'}/><div className="table-wrap"><table><thead><tr><th>STUDENT</th><th>COURSE</th><th>SEMESTER</th><th>SCORE</th><th>GRADE</th><th></th></tr></thead><tbody>{results.map(r=><tr key={r.id}><td><div className="student-cell"><div className="student-avatar">{(r.first_name[0]+r.last_name[0]).toUpperCase()}</div><div><b>{r.first_name} {r.last_name}</b><span>{r.matric_number}</span></div></div></td><td><b>{r.course_code}</b><div className="muted-cell">{r.course_title}</div></td><td>{r.semester}</td><td className="score-cell">{r.score.toFixed(1)}%</td><td><span className="grade-pill">{grade(r.score)}</span></td><td><button className="row-action danger-action" title="Delete result" onClick={()=>void deleteResult(r)}><Trash2 size={15}/></button></td></tr>)}</tbody></table>{!results.length&&<Empty icon={BookOpen} title="No results recorded" detail="Record a course result to see it here."/>}</div></section>
        </>}
        {page==='Backup & Recovery'&&<>
          <PageHeading eyebrow="DATA PROTECTION" title="Backup & recovery" description="Protect your records with verified database snapshots." action={<button className="primary-button" onClick={()=>void createBackup()}><Plus size={17}/> Create backup</button>}/>
          <div className="recovery-callout"><div className="callout-icon"><ShieldCheck size={21}/></div><div><b>Your database is ready for protection</b><p>Snapshots are stored in PostgreSQL, validated before restoration, and protected by a pre-restore safety snapshot.</p></div><span className="secure-pill"><i/> Integrity checks enabled</span></div>
          <section className="panel table-panel"><div className="table-toolbar"><div><h2>Backup history <span className="count-pill">{backups.length}</span></h2><p>Snapshots stored in Neon PostgreSQL</p></div><button className="filter-button" onClick={()=>void refresh()}><RefreshCw size={15}/> Refresh</button></div>
            {backups.length?<div className="backup-list">{backups.map(b=><div className="backup-row" key={b.filename}><div className="file-icon"><Database size={19}/></div><div className="backup-file"><b>{b.filename}</b><span>{dateLabel(b.modified_at)} · {bytes(b.size_bytes)}</span></div><span className="verified"><Check size={14}/> Available</span><button className="restore-button" onClick={()=>void restoreBackup(b.filename)}><ArrowDownToLine size={15}/> Restore</button></div>)}</div>:<Empty icon={Database} title="No backups created yet" detail="Create your first snapshot to protect the student database."/>}
          </section>
          <div className="recovery-note"><ShieldCheck size={17}/><div><b>Recovery safety</b><span>The current database is preserved as a separate safety copy before a restore.</span></div></div>
        </>}
        {page==='Activity Log'&&<>
          <PageHeading eyebrow="SYSTEM AUDIT TRAIL" title="Activity log" description="A chronological record of important system actions." action={<button className="filter-button" onClick={()=>void refresh()}><RefreshCw size={15}/> Refresh</button>}/>
          <section className="panel table-panel"><PanelHead title="All activity" subtitle={activity.length+' recent system events'}/><ActivityList rows={activity}/></section>
        </>}
        <footer className="footer"><span>© 2026 CampusBook · Academic project</span><span>Built for reliable student records <span className="footer-heart">♥</span></span></footer>
      </div>
    </main>
    {studentModal&&<Modal onClose={()=>setStudentModal(false)} eyebrow="STUDENT RECORD" title={editingStudent?'Edit student':'Add a student'} description="Enter the student's information below."><form onSubmit={saveStudent}><div className="form-grid">
      <label>First name<input required value={studentForm.first_name} onChange={e=>setStudentForm({...studentForm,first_name:e.target.value})}/></label>
      <label>Last name<input required value={studentForm.last_name} onChange={e=>setStudentForm({...studentForm,last_name:e.target.value})}/></label>
      <label className="full">Matriculation number<input required value={studentForm.matric_number} onChange={e=>setStudentForm({...studentForm,matric_number:e.target.value})} placeholder="e.g. RSU/2024/CPE/001"/></label>
      
      <label>Department<select value={studentForm.department} onChange={e=>setStudentForm({...studentForm,department:e.target.value})}>{departments.map(d=><option key={d.id}>{d.name}</option>)}</select></label>
      <label>Level<select value={studentForm.level} onChange={e=>setStudentForm({...studentForm,level:e.target.value})}>{['100','200','300','400','500'].map(v=><option key={v}>{v}</option>)}</select></label>
      <label>Status<select value={studentForm.status} onChange={e=>setStudentForm({...studentForm,status:e.target.value})}><option>Active</option><option>Inactive</option></select></label>
    </div><ModalActions onCancel={()=>setStudentModal(false)} saving={saving} submit={editingStudent?'Save changes':'Save student'}/></form></Modal>}
    {departmentModal&&<Modal onClose={()=>setDepartmentModal(false)} eyebrow="ACADEMIC STRUCTURE" title="Add department" description="Create a department in the institution directory."><form onSubmit={saveDepartment}><div className="form-grid"><label className="full">Department name<input required minLength={2} value={departmentForm.name} onChange={e=>setDepartmentForm({...departmentForm,name:e.target.value})}/></label><label className="full">Department code<input required minLength={2} maxLength={12} value={departmentForm.code} onChange={e=>setDepartmentForm({...departmentForm,code:e.target.value.toUpperCase()})} placeholder="e.g. CPE"/></label></div><ModalActions onCancel={()=>setDepartmentModal(false)} saving={saving} submit="Add department"/></form></Modal>}
    {resultModal&&<Modal onClose={()=>setResultModal(false)} eyebrow="ACADEMIC PERFORMANCE" title="Record a result" description="Enter the course result and select the student."><form onSubmit={saveResult}><div className="form-grid"><label className="full">Student<select required value={resultForm.student_id} onChange={e=>setResultForm({...resultForm,student_id:e.target.value})}><option value="">Select a student</option>{students.map(s=><option key={s.id} value={s.id}>{s.first_name} {s.last_name} — {s.matric_number}</option>)}</select></label><label>Course code<input required value={resultForm.course_code} onChange={e=>setResultForm({...resultForm,course_code:e.target.value.toUpperCase()})} placeholder="CPE 301"/></label><label>Score (0–100)<input required type="number" min="0" max="100" step="0.1" value={resultForm.score} onChange={e=>setResultForm({...resultForm,score:e.target.value})}/></label><label className="full">Course title<input required value={resultForm.course_title} onChange={e=>setResultForm({...resultForm,course_title:e.target.value})}/></label><label className="full">Semester<input required value={resultForm.semester} onChange={e=>setResultForm({...resultForm,semester:e.target.value})}/></label></div><ModalActions onCancel={()=>setResultModal(false)} saving={saving} submit="Save result"/></form></Modal>}
  </div>;
}

function grade(score:number){return score>=70?'A':score>=60?'B':score>=50?'C':score>=45?'D':score>=40?'E':'F';}
function PageHeading({eyebrow,title,description,action}:{eyebrow:string;title:string;description:string;action?:ReactNode}){return <div className="page-heading"><div><div className="eyebrow">{eyebrow}</div><h1>{title}</h1><p>{description}</p></div>{action}</div>;}
function Stat({icon:Icon,label,value,note,tone}:{icon:any;label:string;value:any;note:string;tone:string}){return <div className="stat-card"><div className={'stat-icon '+tone}><Icon size={19}/></div><div className="stat-label">{label}</div><div className="stat-value">{value}</div><div className="stat-note">{note}</div></div>;}
function PanelHead({title,subtitle,action}:{title:string;subtitle:string;action?:ReactNode}){return <div className="panel-head"><div><h2>{title}</h2><p>{subtitle}</p></div>{action}</div>;}
function StudentTable({rows,onEdit,onDelete}:{rows:Student[];onEdit:(s:Student)=>void;onDelete:(s:Student)=>void}){return <div className="table-wrap"><table><thead><tr><th>STUDENT</th><th>MATRIC NUMBER</th><th>DEPARTMENT</th><th>LEVEL</th><th>STATUS</th><th></th></tr></thead><tbody>{rows.map(s=><tr key={s.id}><td><div className="student-cell"><div className="student-avatar">{initials(s)}</div><div><b>{s.first_name} {s.last_name}</b></div></div></td><td className="mono">{s.matric_number}</td><td>{s.department}</td><td>{s.level} Level</td><td><span className={'status '+(s.status==='Active'?'status-active':'status-inactive')}><i/>{s.status}</span></td><td><div className="row-actions"><button className="row-action" title="Edit student" onClick={()=>onEdit(s)}><Pencil size={14}/></button><button className="row-action danger-action" title="Delete student" onClick={()=>void onDelete(s)}><Trash2 size={14}/></button></div></td></tr>)}</tbody></table>{!rows.length&&<Empty icon={Users} title="No student records" detail="Add a student to get started."/>}</div>;}
function ActivityList({rows}:{rows:ActivityItem[]}){return rows.length?<div className="activity-list">{rows.map(a=><div className="activity-row" key={a.id}><div className="activity-icon"><Activity size={15}/></div><div><b>{a.action}</b><span>{a.details}</span><small>{dateLabel(a.created_at)}</small></div></div>)}</div>:<Empty icon={Activity} title="No activity yet" detail="System events will appear here as you work."/>;}
function Empty({icon:Icon,title,detail}:{icon:any;title:string;detail:string}){return <div className="empty-state"><div><Icon size={22}/></div><b>{title}</b><span>{detail}</span></div>;}
function Modal({children,onClose,eyebrow,title,description}:{children:ReactNode;onClose:()=>void;eyebrow:string;title:string;description:string}){return <div className="modal-backdrop" onClick={onClose}><section className="modal" onClick={e=>e.stopPropagation()}><div className="modal-head"><div><div className="eyebrow">{eyebrow}</div><h2>{title}</h2><p>{description}</p></div><button type="button" className="icon-button" onClick={onClose}><X size={18}/></button></div>{children}</section></div>;}
function ModalActions({onCancel,saving,submit}:{onCancel:()=>void;saving:boolean;submit:string}){return <div className="modal-actions"><button type="button" className="secondary-button" onClick={onCancel}>Cancel</button><button className="primary-button" disabled={saving}>{saving?'Saving…':submit}</button></div>;}

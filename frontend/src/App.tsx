import { useEffect, useMemo, useState } from 'react';
import type { FormEvent, ReactNode } from 'react';
import {
  Activity, ArrowDownToLine, BookOpen, Building2, Check, Menu,
  ChevronRight, Database, GraduationCap, LayoutDashboard,
  Plus, Search, ShieldCheck, Users, X, Pencil, Trash2,
  RefreshCw,
} from 'lucide-react';

const API = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\\/$/,'');
type AuthUser={id:number;username:string;role:'Administrator'|'Lecturer'|'Student';student_id:number|null;lecturer_id:number|null};
type Offering={id:number;course_code:string;course_title:string;credit_units:number;level:string;department:string;semester:string;academic_session:string;section:string;status:string};
type RosterRow={student_id:number;matric_number:string;first_name:string;last_name:string;score:number|null;grade_status:string|null};
type Student = {
  id:number; matric_number:string; first_name:string; last_name:string;
  department:string; department_id:number; faculty:string; level:string; status:string; created_at:string;
};
type Department = {id:number;name:string;code:string;faculty_id:number;faculty_name:string;student_count:number};
type Faculty = {id:number;name:string;code:string;department_count:number};
type GradeSubmission={offering_id:number;course_code:string;course_title:string;section:string;semester:string;academic_session:string;lecturer_first_name:string|null;lecturer_last_name:string|null;roster_count:number;submitted_count:number;published_count:number};
type Result = {id:number;student_id:number;course_code:string;course_title:string;score:number;semester:string;matric_number:string;first_name:string;last_name:string};
type Backup = {filename:string;size_bytes:number;modified_at:string};
type ActivityItem = {id:number;action:string;details:string;created_at:string};
type Dashboard = {total_students:number;active_students:number;departments:number;available_backups:number;recent_activity:ActivityItem[];students_by_department:{name:string;count:number}[]};
type StudentForm = Omit<Student,'id'|'created_at'>;

class ApiError extends Error {
  constructor(message:string,readonly status:number){super(message);this.name='ApiError';}
}
async function request<T=any>(path:string, options?:RequestInit):Promise<T> {
  const response = await fetch(API+path,{credentials:'include',...options,headers:{'Content-Type':'application/json',...(options?.headers||{})}});
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
      const transient=(error instanceof ApiError&&[500,502,503,504].includes(error.status))||error instanceof TypeError;
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


function PortalFrame({user,onLogout,children}:{user:AuthUser;onLogout:()=>void;children:ReactNode}){
 return <div className="portal-shell"><header className="portal-header"><div className="portal-brand"><div className="brand-mark"><GraduationCap size={21}/></div><span>campus<span className="brand-light">book</span></span></div><div className="portal-user"><span>{user.username}</span><button className="secondary-button" onClick={onLogout}>Sign out</button></div></header><main className="portal-content">{children}</main></div>;
}
function StudentPortal({user,onLogout}:{user:AuthUser;onLogout:()=>void}){
 const [offerings,setOfferings]=useState<Offering[]>([]),[registrations,setRegistrations]=useState<any[]>([]),[results,setResults]=useState<any[]>([]);
 const [loading,setLoading]=useState(true),[error,setError]=useState(''),[notice,setNotice]=useState('');
 async function load(){setLoading(true);setError('');try{const [o,r,g]=await Promise.all([request<Offering[]>('/api/course-offerings'),request<any[]>('/api/student/registrations'),request<any[]>('/api/student/results')]);setOfferings(o);setRegistrations(r);setResults(g);}catch(e){setError(e instanceof Error?e.message:'Could not load academic information.');}finally{setLoading(false);}}
 useEffect(()=>{void load();},[]);
 async function register(id:number){try{await request('/api/student/course-offerings/'+id+'/register',{method:'POST'});setNotice('Course registered.');await load();}catch(e){setNotice(e instanceof Error?e.message:'Registration failed.');}}
 async function drop(id:number){if(!window.confirm('Drop this course?'))return;try{await request('/api/student/course-offerings/'+id+'/register',{method:'DELETE'});setNotice('Course dropped.');await load();}catch(e){setNotice(e instanceof Error?e.message:'Could not drop course.');}}
 return <PortalFrame user={user} onLogout={onLogout}><div className="portal-heading"><div><p className="eyebrow">STUDENT WORKSPACE</p><h1>My academic space</h1><p>Register for courses, review your selections and check published results.</p></div><span className="role-chip">Student</span></div>
 {notice&&<div className="portal-notice">{notice}<button onClick={()=>setNotice('')}>Dismiss</button></div>}{error&&<div className="portal-error">{error}<button onClick={()=>void load()}>Retry</button></div>}
 {loading?<div className="portal-card">Loading academic information…</div>:<>
 <section className="portal-section"><div className="portal-section-heading"><h2>Available courses</h2><span>{offerings.length} available</span></div>{offerings.length===0?<div className="portal-empty">No courses are open for your department and level right now.</div>:<div className="portal-course-grid">{offerings.map(o=><article className="portal-card" key={o.id}><div className="course-code">{o.course_code}</div><h3>{o.course_title}</h3><p>{o.department} · {o.level} Level</p><div className="course-meta">{o.academic_session} · {o.semester} · Section {o.section}</div><button className="primary-button" onClick={()=>void register(o.id)}>Register for course</button></article>)}</div>}</section>
 <section className="portal-section"><div className="portal-section-heading"><h2>My registered courses</h2><span>{registrations.filter(r=>r.status==='Registered').length} active</span></div>{registrations.length===0?<div className="portal-empty">You have not registered for any courses yet.</div>:<div className="portal-table-wrap"><table className="portal-table"><thead><tr><th>Course</th><th>Session / Semester</th><th>Status</th><th></th></tr></thead><tbody>{registrations.map(r=><tr key={r.id}><td><b>{r.course_code}</b><span>{r.course_title}</span></td><td>{r.academic_session} · {r.semester}</td><td>{r.status}</td><td>{r.status==='Registered'&&<button className="text-action" onClick={()=>void drop(r.id)}>Drop</button>}</td></tr>)}</tbody></table></div>}</section>
 <section className="portal-section"><div className="portal-section-heading"><h2>Published results</h2><span>{results.length} results</span></div>{results.length===0?<div className="portal-empty">Published results will appear here after approval.</div>:<div className="portal-table-wrap"><table className="portal-table"><thead><tr><th>Course</th><th>Session / Semester</th><th>Score</th><th>Grade</th></tr></thead><tbody>{results.map((r,i)=><tr key={i}><td><b>{r.course_code}</b><span>{r.course_title}</span></td><td>{r.academic_session} · {r.semester}</td><td>{r.score}</td><td>{r.letter_grade||'—'}</td></tr>)}</tbody></table></div>}</section>
 </>}</PortalFrame>;
}
function LecturerPortal({user,onLogout}:{user:AuthUser;onLogout:()=>void}){
 const [offerings,setOfferings]=useState<Offering[]>([]),[selected,setSelected]=useState<number|''>(''),[roster,setRoster]=useState<RosterRow[]>([]);
 const [scores,setScores]=useState<Record<number,string>>({}),[loading,setLoading]=useState(true),[saving,setSaving]=useState(false),[notice,setNotice]=useState(''),[error,setError]=useState('');
 async function loadOfferings(){setLoading(true);setError('');try{const data=await request<Offering[]>('/api/course-offerings');setOfferings(data);if(data.length&&!selected)setSelected(data[0].id);}catch(e){setError(e instanceof Error?e.message:'Could not load assigned courses.');}finally{setLoading(false);}}
 async function loadRoster(id:number){try{const data=await request<RosterRow[]>('/api/lecturer/offerings/'+id+'/roster');setRoster(data);setScores(Object.fromEntries(data.map(r=>[r.student_id,r.score===null?'':String(r.score)])));}catch(e){setError(e instanceof Error?e.message:'Could not load class roster.');}}
 useEffect(()=>{void loadOfferings();},[]);
 useEffect(()=>{if(selected)void loadRoster(selected);},[selected]);
 async function importCsv(file?:File){if(!file||!selected)return;const lines=(await file.text()).trim().split(/\\r?\\n/);const parsed=new Map<string,string>();for(const line of lines.slice(1)){const parts=line.split(',').map(x=>x.trim());if(parts[0]&&parts[1])parsed.set(parts[0],parts[1]);}let matched=0;const next={...scores};for(const row of roster){if(parsed.has(row.matric_number)){next[row.student_id]=parsed.get(row.matric_number)!;matched++;}}setScores(next);setNotice('Imported '+matched+' matching scores. Review before saving.');}
 async function save(submit=false){if(!selected)return;setSaving(true);setError('');try{const grades=roster.filter(r=>(scores[r.student_id]||'').trim()!=='').map(r=>({student_id:r.student_id,score:Number(scores[r.student_id])}));if(grades.some(g=>!Number.isFinite(g.score)||g.score<0||g.score>100))throw new Error('Scores must be between 0 and 100.');await request('/api/lecturer/offerings/'+selected+'/grades',{method:'PUT',body:JSON.stringify({grades})});if(submit){await request('/api/lecturer/offerings/'+selected+'/submit',{method:'POST'});setNotice('Grade roster submitted for administrator approval.');}else setNotice('Draft grades saved.');await loadRoster(selected);}catch(e){setError(e instanceof Error?e.message:'Could not save grade roster.');}finally{setSaving(false);}}
 const current=offerings.find(o=>o.id===selected);
 return <PortalFrame user={user} onLogout={onLogout}><div className="portal-heading"><div><p className="eyebrow">LECTURER WORKSPACE</p><h1>My courses</h1><p>Review assigned class rosters and submit student marks.</p></div><span className="role-chip">Lecturer</span></div>
 {notice&&<div className="portal-notice">{notice}<button onClick={()=>setNotice('')}>Dismiss</button></div>}{error&&<div className="portal-error">{error}<button onClick={()=>selected?void loadRoster(selected):void loadOfferings()}>Retry</button></div>}
 {loading?<div className="portal-card">Loading assigned courses…</div>:offerings.length===0?<div className="portal-empty">No course offerings have been assigned to your account.</div>:<>
 <section className="portal-card lecturer-course-select"><label htmlFor="lecturer-course">Select course offering</label><select id="lecturer-course" value={selected} onChange={e=>setSelected(Number(e.target.value))}>{offerings.map(o=><option value={o.id} key={o.id}>{o.course_code} — {o.course_title} · {o.academic_session} {o.semester}</option>)}</select>{current&&<p>{current.department} · Section {current.section} · {current.level} Level</p>}</section>
 <section className="portal-section"><div className="portal-section-heading"><div><h2>Class grade roster</h2><span>Enter total scores from 0 to 100</span></div><div className="portal-import"><a href={'data:text/csv;charset=utf-8,'+encodeURIComponent('matric_number,score\\n'+roster.map(r=>r.matric_number+',').join('\\n'))} download="campusbook-grade-template.csv">Download CSV template</a><label className="secondary-button">Import CSV<input type="file" accept=".csv,text/csv" onChange={e=>void importCsv(e.target.files?.[0])}/></label></div></div>
 {roster.length===0?<div className="portal-empty">No students are registered for this course yet.</div>:<div className="portal-table-wrap"><table className="portal-table"><thead><tr><th>Matriculation number</th><th>Student</th><th>Total score / 100</th><th>State</th></tr></thead><tbody>{roster.map(r=><tr key={r.student_id}><td><b>{r.matric_number}</b></td><td>{r.first_name} {r.last_name}</td><td><input className="score-input" type="number" min="0" max="100" step="0.5" value={scores[r.student_id]??''} onChange={e=>setScores(v=>({...v,[r.student_id]:e.target.value}))}/></td><td>{r.grade_status||'Not entered'}</td></tr>)}</tbody></table></div>}
 <div className="portal-actions"><button className="secondary-button" disabled={saving||!roster.length} onClick={()=>void save(false)}>Save draft</button><button className="primary-button" disabled={saving||!roster.length} onClick={()=>void save(true)}>Submit completed roster</button></div></section>
 </>}</PortalFrame>;
}

export default function App(){
  const [page,setPage]=useState('Overview');
  const [user,setUser]=useState<AuthUser|null>(null);
  const [authLoading,setAuthLoading]=useState(true);
  const [loginUsername,setLoginUsername]=useState('');
  const [loginPassword,setLoginPassword]=useState('');
  const [loginError,setLoginError]=useState('');
  const [mobileNavOpen,setMobileNavOpen]=useState(false);
  const [dashboard,setDashboard]=useState<Dashboard|null>(null);
  const [students,setStudents]=useState<Student[]>([]);
  const [departments,setDepartments]=useState<Department[]>([]);
  const [faculties,setFaculties]=useState<Faculty[]>([]);
  const [gradeSubmissions,setGradeSubmissions]=useState<GradeSubmission[]>([]);
  const [results,setResults]=useState<Result[]>([]);
  const [backups,setBackups]=useState<Backup[]>([]);
  const [activity,setActivity]=useState<ActivityItem[]>([]);
  const [search,setSearch]=useState('');
  const [studentStatus,setStudentStatus]=useState('All');
  const [studentDepartment,setStudentDepartment]=useState('All');
  const [studentFaculty,setStudentFaculty]=useState('All');
  const [loading,setLoading]=useState(true);
  const [error,setError]=useState('');
  const [notice,setNotice]=useState('');
  const [studentModal,setStudentModal]=useState(false);
  const [editingStudent,setEditingStudent]=useState<Student|null>(null);
  const [studentForm,setStudentForm]=useState<StudentForm>(emptyStudent);
  const [resultModal,setResultModal]=useState(false);
  const [resultForm,setResultForm]=useState({student_id:'',course_code:'',course_title:'',score:'',semester:'First Semester 2026/2027'});
  const [departmentModal,setDepartmentModal]=useState(false);
  const [departmentForm,setDepartmentForm]=useState({name:'',code:'',faculty_id:''});
  const [saving,setSaving]=useState(false);

  async function refresh(){
    setLoading(true);setError('');
    try{
      const [d,s,de,fa,r,b,a,gs]=await Promise.all([
        requestWithRetry<Dashboard>('/api/dashboard'),requestWithRetry<Student[]>('/api/students'),
        requestWithRetry<Department[]>('/api/departments'),requestWithRetry<Faculty[]>('/api/faculties'),requestWithRetry<Result[]>('/api/results'),
        requestWithRetry<Backup[]>('/api/backups'),requestWithRetry<ActivityItem[]>('/api/activity'),requestWithRetry<GradeSubmission[]>('/api/admin/grade-submissions'),
      ]);
      setDashboard(d);setStudents(s);setDepartments(de);setFaculties(fa);setResults(r);setBackups(b);setActivity(a);setGradeSubmissions(gs);
    }catch(e){setError(e instanceof Error?e.message:'Could not connect to the API.');}
    finally{setLoading(false);}
  }
  useEffect(()=>{request<AuthUser>('/api/auth/me').then(setUser).catch(()=>setUser(null)).finally(()=>setAuthLoading(false));},[]);
  useEffect(()=>{if(user?.role==='Administrator')void refresh();},[user]);
  useEffect(()=>{if(!notice)return;const t=window.setTimeout(()=>setNotice(''),4000);return()=>window.clearTimeout(t);},[notice]);

  async function submitLogin(e:FormEvent){e.preventDefault();setLoginError('');try{const account=await request<AuthUser>('/api/auth/login',{method:'POST',body:JSON.stringify({username:loginUsername,password:loginPassword})});setUser(account);setLoginPassword('');}catch(e){setLoginError(e instanceof Error?e.message:'Unable to sign in.');}}
  async function signOut(){try{await request('/api/auth/logout',{method:'POST'});}finally{setUser(null);setDashboard(null);setStudents([]);setResults([]);setBackups([]);setActivity([]);}}
  const filteredStudents=useMemo(()=>students.filter(s=>{
    const matchesSearch=[s.first_name,s.last_name,s.matric_number,s.department].join(' ').toLowerCase().includes(search.toLowerCase());
    const matchesStatus=studentStatus==='All'||s.status===studentStatus;
    const matchesDepartment=studentDepartment==='All'||s.department===studentDepartment;
    const matchesFaculty=studentFaculty==='All'||s.faculty===studentFaculty;
    return matchesSearch&&matchesStatus&&matchesDepartment&&matchesFaculty;
  }),[students,search,studentStatus,studentDepartment,studentFaculty]);

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
    try{await request('/api/departments',{method:'POST',body:JSON.stringify({...departmentForm,faculty_id:Number(departmentForm.faculty_id)})});setDepartmentModal(false);setDepartmentForm({name:'',code:'',faculty_id:''});setNotice('Department added.');await refresh();}
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
  if(authLoading)return <div className="auth-screen"><div className="auth-card"><div className="portal-brand"><div className="brand-mark"><GraduationCap size={21}/></div><span>campus<span className="brand-light">book</span></span></div><p>Checking your session…</p></div></div>;
  if(!user)return <div className="auth-screen"><form className="auth-card" onSubmit={submitLogin}><div className="portal-brand"><div className="brand-mark"><GraduationCap size={21}/></div><span>campus<span className="brand-light">book</span></span></div><p className="eyebrow">STUDENT RECORDS & COURSE REGISTRATION</p><h1>Sign in to CampusBook</h1><p className="auth-description">Use the account provided by your institution.</p>{loginError&&<div className="portal-error">{loginError}</div>}<label>Username<input autoComplete="username" value={loginUsername} onChange={e=>setLoginUsername(e.target.value)} required/></label><label>Password<input type="password" autoComplete="current-password" value={loginPassword} onChange={e=>setLoginPassword(e.target.value)} required/></label><button className="primary-button" type="submit">Sign in</button><small>Accounts are created by the institution. Public sign-up is disabled.</small></form></div>;
  if(user.role==='Student')return <StudentPortal user={user} onLogout={()=>void signOut()}/>;
  if(user.role==='Lecturer')return <LecturerPortal user={user} onLogout={()=>void signOut()}/>;
  return <div className="app-shell">
    <aside className={'sidebar '+(mobileNavOpen?'mobile-open':'')}>
      <div className="mobile-brand"><div className="brand-mark"><GraduationCap size={21}/></div><span>campus<span className="brand-light">book</span></span></div>
      <div className="brand"><div className="brand-mark"><GraduationCap size={21}/></div><span>campus<span className="brand-light">book</span></span></div>
      <div className="workspace"><div className="workspace-avatar">RS</div><div><b>Rivers State University</b><small>Academic records</small></div></div>
      <div className="nav-label">WORKSPACE</div>
      <nav>{nav.map(item=><button key={item.label} className={'nav-item '+(page===item.label?'active':'')} onClick={()=>{setPage(item.label);setMobileNavOpen(false);}}><item.icon size={18}/><span>{item.label}</span>{item.label==='Backup & Recovery'&&<i className="nav-dot"/>}</button>)}</nav>
      <div className="sidebar-bottom"><div className="profile"><div className="profile-avatar">CA</div><div><b>{user.username}</b><small>Administrator</small></div></div></div>
    </aside>
    <main className="main">
      <header className="topbar"><button className="mobile-menu-button" aria-label="Open navigation" onClick={()=>setMobileNavOpen(v=>!v)}><Menu size={20}/></button><div className="breadcrumb"><span>Workspace</span><ChevronRight size={14}/><b>{page}</b></div><div className="top-actions"><div className="system-status"><i/>System operational</div><span className="admin-user-label">{user.username}</span><button className="secondary-button signout-button" onClick={()=>void signOut()}>Sign out</button></div></header>
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

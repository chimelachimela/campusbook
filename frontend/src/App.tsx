import { useEffect, useMemo, useState } from 'react';
import type { FormEvent, ReactNode } from 'react';
import AdminWorkspace from './AdminWorkspace';
import ExamsOfficerPortal from './ExamsOfficerPortal';
import {
  Activity, ArrowDownToLine, BookOpen, Building2, Check, Menu,
  ChevronRight, Database, GraduationCap, LayoutDashboard,
  Plus, Search, ShieldCheck, Users, X, Pencil, Trash2,
  RefreshCw,
} from 'lucide-react';

const API = import.meta.env.VITE_API_URL ?? (import.meta.env.PROD ? '' : 'http://localhost:8000');
const demoMode = import.meta.env.VITE_DEMO_MODE === 'true';
type AuthUser={id:number;username:string;role:'Administrator'|'Lecturer'|'Student'|'ExamsOfficer';student_id:number|null;lecturer_id:number|null};
type Offering={id:number;course_code:string;course_title:string;credit_units:number;level:string;department:string;semester:string;academic_session:string;section:string;status:string};
type RosterRow={student_id:number;matric_number:string;first_name:string;last_name:string;score:number|null;grade_status:string|null;registration_status?:string|null};
type Student = {
  id:number; matric_number:string; first_name:string; last_name:string;
  department:string; department_id:number; faculty:string; level:string; status:string; created_at:string;
};
type Department = {id:number;name:string;code:string;faculty_id:number;faculty_name:string;student_count:number};
type Faculty = {id:number;name:string;code:string;department_count:number};
type Course={id:number;course_code:string;title:string;credit_units:number;level:string;department:string;department_id:number};
type Lecturer={id:number;staff_number:string;first_name:string;last_name:string;department:string};
type AcademicSession={id:number;name:string;is_current:boolean};
type Semester={id:number;academic_session_id:number;name:string};
type GradeSubmission={offering_id:number;course_code:string;course_title:string;section:string;semester:string;academic_session:string;lecturer_first_name:string|null;lecturer_last_name:string|null;roster_count:number;submitted_count:number;published_count:number};
type Result = {id:number;student_id:number;course_code:string;course_title:string;score:number;semester:string;matric_number:string;first_name:string;last_name:string};
type Backup = {filename:string;size_bytes:number;modified_at:string};
type ActivityItem = {id:number;action:string;details:string;created_at:string};
type Dashboard = {total_students:number;active_students:number;departments:number;available_backups:number;recent_activity:ActivityItem[];students_by_department:{name:string;count:number}[]};
type StudentForm = Omit<Student,'id'|'created_at'|'department_id'|'faculty'>;

class ApiError extends Error {
  constructor(message:string,readonly status:number){super(message);this.name='ApiError';}
}
async function request<T=any>(path:string, options?:RequestInit):Promise<T> {
  const controller=new AbortController();
  const timeout=window.setTimeout(()=>controller.abort(),15000);
  let response:Response;
  try{
    response=await fetch(API+path,{credentials:'include',...options,signal:controller.signal,headers:{'Content-Type':'application/json',...(options?.headers||{})}});
  }finally{window.clearTimeout(timeout);}
  if(!response.ok){const body=await response.json().catch(()=>({}));throw new ApiError(body.detail||(response.status===502||response.status===503||response.status===504?'CampusBook is starting up.':'The request could not be completed.'),response.status);}
  if(response.status===204)return undefined as T;
  return response.json();
}
const wait=(ms:number)=>new Promise(resolve=>window.setTimeout(resolve,ms));
async function requestWithRetry<T>(path:string,attempts=4,options?:RequestInit):Promise<T>{
  let lastError:unknown;
  for(let attempt=0;attempt<attempts;attempt++){
    try{return await request<T>(path,options);}
    catch(error){
      lastError=error;
      const transient=(error instanceof ApiError&&[500,502,503,504].includes(error.status))||error instanceof TypeError||(error instanceof DOMException&&error.name==='AbortError');
      if(!transient||attempt===attempts-1)throw error;
      await wait(Math.min(2000*(2**attempt),8000));
    }
  }
  throw lastError instanceof Error?lastError:new Error('Could not connect to CampusBook.');
}
const emptyStudent:StudentForm={matric_number:'',first_name:'',last_name:'',department:'Computer Engineering',level:'300',status:'Active'};
const dateLabel=(v:string)=>new Date(v).toLocaleString([],{month:'short',day:'numeric',year:'numeric',hour:'2-digit',minute:'2-digit'});
const bytes=(n:number)=>n<1024?n+' B':(n/1024).toFixed(1)+' KB';
const initials=(s:Student)=>(s.first_name[0]+s.last_name[0]).toUpperCase();


function PortalFrame({user,onLogout,children,activePage,onNavigate}:{user:AuthUser;onLogout:()=>void;children:ReactNode;activePage?:string;onNavigate?:(id:string)=>void}){
 const [mobileOpen,setMobileOpen]=useState(false);
 const items=user.role==='Student'?[{label:'Course Registration',id:'course-registration',icon:BookOpen},{label:'My Courses',id:'my-courses',icon:GraduationCap},{label:'Published Results',id:'published-results',icon:Activity},{label:'CGPA Calculator',id:'cgpa-calculator',icon:GraduationCap}]:[{label:'My Courses',id:'lecturer-courses',icon:BookOpen},{label:'Class Grade Roster',id:'grade-roster',icon:Users}];
 return <div className="app-shell">
  <aside className={'sidebar '+(mobileOpen?'mobile-open':'')}>
   <div className="mobile-brand"><div className="brand-mark"><GraduationCap size={21}/></div><span>campus<span className="brand-light">book</span></span></div>
   <div className="brand"><div className="brand-mark"><GraduationCap size={21}/></div><span>campus<span className="brand-light">book</span></span></div>
   <div className="workspace"><div className="workspace-avatar">RS</div><div><b>Rivers State University</b><small>Academic records</small></div></div>
   <div className="nav-label">WORKSPACE</div>
   <nav>{items.map((item,i)=><button key={item.id} className={'nav-item '+((activePage?activePage===item.id:i===0)?'active':'')} onClick={()=>{if(onNavigate)onNavigate(item.id);else document.getElementById(item.id)?.scrollIntoView({behavior:'smooth',block:'start'});setMobileOpen(false);}}><item.icon size={18}/><span>{item.label}</span></button>)}</nav>
   <div className="sidebar-bottom"><div className="profile"><div className="profile-avatar">{user.role==='Student'?'ST':'LE'}</div><div><b>{user.username}</b><small>{user.role}</small></div></div></div>
  </aside>
  <main className="main">
   <header className="topbar"><button className="mobile-menu-button" onClick={()=>setMobileOpen(v=>!v)} aria-label="Toggle navigation"><Menu size={20}/></button><div className="breadcrumb">Workspace <ChevronRight size={14}/> {user.role}</div><div className="admin-user-label">{user.username} · {user.role}</div><button className="secondary-button signout-button" onClick={onLogout}>Sign out</button></header>
   <div className="content">{children}</div>
  </main>
 </div>;
}
function StudentPortal({user,onLogout}:{user:AuthUser;onLogout:()=>void}){
 const [offerings,setOfferings]=useState<Offering[]>([]),[registrations,setRegistrations]=useState<any[]>([]),[results,setResults]=useState<any[]>([]);
 const [selected,setSelected]=useState<number[]>([]),[activePage,setActivePage]=useState('course-registration');
 const [loading,setLoading]=useState(true),[registering,setRegistering]=useState(false),[error,setError]=useState(''),[notice,setNotice]=useState('');
 async function load(){setLoading(true);setError('');try{const [o,r,g]=await Promise.all([requestWithRetry<Offering[]>('/api/course-offerings'),requestWithRetry<any[]>('/api/student/registrations'),requestWithRetry<any[]>('/api/student/results')]);setOfferings(o);setRegistrations(r);setResults(g);const active=new Set(r.filter(x=>x.status==='Registered').map(x=>x.course_offering_id));setSelected(o.filter(x=>active.has(x.id)).map(x=>x.id));}catch(e){setError(e instanceof Error?e.message:'Could not load academic information.');}finally{setLoading(false);}}
 useEffect(()=>{void load();},[]);
 const registered=new Set(registrations.filter(r=>r.status==='Registered').map(r=>r.course_offering_id));
 const toggle=(id:number)=>setSelected(v=>v.includes(id)?v.filter(x=>x!==id):[...v,id]);
 async function registerSelected(){if(!selected.length)return;setRegistering(true);setNotice('');try{const result=await request<{registered:number;already_registered:number}>('/api/student/course-offerings/register',{method:'POST',body:JSON.stringify({course_offering_ids:selected})});setNotice(result.registered+' course(s) registered'+(result.already_registered?', '+result.already_registered+' already registered.':'.'));await load();}catch(e){setNotice(e instanceof Error?e.message:'Course registration failed.');}finally{setRegistering(false);}}
 async function drop(id:number){if(!window.confirm('Drop this course?'))return;try{await request('/api/student/course-offerings/'+id+'/register',{method:'DELETE'});setNotice('Course dropped.');await load();}catch(e){setNotice(e instanceof Error?e.message:'Could not drop course.');}}
 return <PortalFrame user={user} onLogout={onLogout} activePage={activePage} onNavigate={setActivePage}><div className="portal-heading"><div><p className="eyebrow">STUDENT WORKSPACE</p><h1>My academic space</h1><p>Choose your courses for the current session, register, and check published results.</p></div><span className="role-chip">Student</span></div>
 {notice&&<div className="portal-notice">{notice}<button onClick={()=>setNotice('')}>Dismiss</button></div>}{error&&<div className="portal-error">{error}<button onClick={()=>void load()}>Retry</button></div>}
 {loading?<div className="portal-card">Loading academic information…</div>:<>
 {activePage==='course-registration'&&<section id="course-registration" className="portal-section"><div className="portal-section-heading"><div><h2>Course registration</h2><span>{offerings.length} courses available for your department and level</span></div><span>{selected.length} selected</span></div>
 {offerings.length===0?<div className="portal-empty">No courses are open for your department and level right now. Contact your department administrator.</div>:<>
 <div className="portal-table-wrap"><table className="portal-table"><thead><tr><th>Select</th><th>Course</th><th>Units</th><th>Lecturer</th><th>Session / Semester</th><th>Status</th></tr></thead><tbody>{offerings.map(o=><tr key={o.id}><td><input aria-label={'Select '+o.course_code} type="checkbox" checked={selected.includes(o.id)} disabled={registered.has(o.id)} onChange={()=>toggle(o.id)}/></td><td><b>{o.course_code}</b><span>{o.course_title}</span></td><td>{o.credit_units}</td><td>{(o as any).lecturer_first_name?((o as any).lecturer_first_name+' '+(o as any).lecturer_last_name):'To be assigned'}</td><td>{o.academic_session} · {o.semester}</td><td>{registered.has(o.id)?'Registered':'Available'}</td></tr>)}</tbody></table></div>
 <div className="portal-actions"><button className="secondary-button" onClick={()=>setSelected(offerings.filter(o=>!registered.has(o.id)).map(o=>o.id))}>Select all available</button><button className="primary-button" disabled={registering||!selected.some(id=>!registered.has(id))} onClick={()=>void registerSelected()}>{registering?'Registering…':'Register selected courses'}</button></div>
 </>}</section>}
 {activePage==='my-courses'&&<section id="my-courses" className="portal-section"><div className="portal-section-heading"><h2>My registered courses</h2><span>{registrations.filter(r=>r.status==='Registered').length} active</span></div>{registrations.length===0?<div className="portal-empty">You have not registered for any courses yet.</div>:<div className="portal-table-wrap"><table className="portal-table"><thead><tr><th>Course</th><th>Session / Semester</th><th>Status</th><th></th></tr></thead><tbody>{registrations.map(r=><tr key={r.id}><td><b>{r.course_code}</b><span>{r.course_title}</span></td><td>{r.academic_session} · {r.semester}</td><td>{r.status}</td><td>{r.status==='Registered'&&<button className="text-action" onClick={()=>void drop(r.course_offering_id)}>Drop</button>}</td></tr>)}</tbody></table></div>}</section>}
 {activePage==='published-results'&&<section id="published-results" className="portal-section"><div className="portal-section-heading"><h2>Published results</h2><span>{results.length} results</span></div>{results.length===0?<div className="portal-empty">Results will appear here after your departmental examination officer submits the results and the administrator publishes them.</div>:<div className="portal-table-wrap"><table className="portal-table"><thead><tr><th>Course</th><th>Session / Semester</th><th>Score</th><th>Grade</th></tr></thead><tbody>{results.map((r,i)=><tr key={i}><td><b>{r.course_code}</b><span>{r.course_title}</span></td><td>{r.academic_session} · {r.semester}</td><td>{r.score}</td><td>{r.letter_grade||'—'}</td></tr>)}</tbody></table></div>}</section>}
 {activePage==='cgpa-calculator'&&<section id="cgpa-calculator" className="portal-section"><div className="portal-section-heading"><div><h2>CGPA calculator</h2><span>Calculated from published grades and registered course credit units on a 5.0 scale.</span></div><span>{results.length} published courses</span></div>{results.length===0?<div className="portal-empty">Your CGPA will appear when your results have been published.</div>:<><div className="cgpa-summary"><span>Current CGPA</span><strong>{(()=>{const units=results.reduce((n,r)=>n+Number(r.credit_units||0),0);const points=results.reduce((n,r)=>n+Number(r.credit_units||0)*({A:5,B:4,C:3,D:2,E:1,F:0}[r.letter_grade as 'A'|'B'|'C'|'D'|'E'|'F']??0),0);return units?(points/units).toFixed(2):'—';})()}</strong><small>Weighted grade points ÷ total published credit units</small></div><div className="portal-table-wrap"><table className="portal-table"><thead><tr><th>Course</th><th>Credit units</th><th>Score</th><th>Grade</th><th>Grade points</th></tr></thead><tbody>{results.map((r,i)=><tr key={i}><td><b>{r.course_code}</b><span>{r.course_title}</span></td><td>{r.credit_units}</td><td>{r.score}</td><td>{r.letter_grade||'—'}</td><td>{{A:5,B:4,C:3,D:2,E:1,F:0}[r.letter_grade as 'A'|'B'|'C'|'D'|'E'|'F']??'—'}</td></tr>)}</tbody></table></div></>}</section>}
 </>}</PortalFrame>;
}
function LecturerPortal({user,onLogout}:{user:AuthUser;onLogout:()=>void}){
 const [offerings,setOfferings]=useState<Offering[]>([]),[selected,setSelected]=useState<number|''>(''),[roster,setRoster]=useState<RosterRow[]>([]),[loading,setLoading]=useState(true),[error,setError]=useState('');
 async function load(){setLoading(true);setError('');try{const data=await requestWithRetry<Offering[]>('/api/course-offerings');setOfferings(data);if(data.length)setSelected(data[0].id);}catch(e){setError(e instanceof Error?e.message:'Could not load assigned courses.');}finally{setLoading(false);}}
 async function loadRoster(id:number){try{setRoster(await requestWithRetry<RosterRow[]>('/api/lecturer/offerings/'+id+'/roster'));}catch(e){setError(e instanceof Error?e.message:'Could not load class roster.');}}
 useEffect(()=>{void load();},[]);useEffect(()=>{if(selected)void loadRoster(selected);},[selected]);
 const current=offerings.find(o=>o.id===selected);
 return <PortalFrame user={user} onLogout={onLogout}><div className="portal-heading"><div><p className="eyebrow">LECTURER WORKSPACE</p><h1>My assigned courses</h1><p>View your assigned courses and registered class lists. Departmental examination officers handle result entry.</p></div><span className="role-chip">Lecturer · Read only</span></div>
 {error&&<div className="portal-error">{error}<button onClick={()=>selected?void loadRoster(selected):void load()}>Retry</button></div>}
 {loading?<div className="portal-card">Loading assigned courses…</div>:offerings.length===0?<div className="portal-empty">No course offerings have been assigned to your account.</div>:<>
 <section className="portal-card lecturer-course-select"><label htmlFor="lecturer-course">Assigned course</label><select id="lecturer-course" value={selected} onChange={e=>setSelected(Number(e.target.value))}>{offerings.map(o=><option value={o.id} key={o.id}>{o.course_code} — {o.course_title} · {o.academic_session} {o.semester}</option>)}</select>{current&&<p>{current.department} · Section {current.section} · {current.level} Level</p>}</section>
 <section className="portal-section"><div className="portal-section-heading"><div><h2>Registered students</h2><span>Read-only class roster · Result entry is handled by the departmental examination officer</span></div><span>{roster.length} students</span></div>{roster.length===0?<div className="portal-empty">No students have registered for this course yet.</div>:<div className="portal-table-wrap"><table className="portal-table"><thead><tr><th>Matriculation number</th><th>Student</th><th>Registration</th></tr></thead><tbody>{roster.map(r=><tr key={r.student_id}><td><b>{r.matric_number}</b></td><td>{r.first_name} {r.last_name}</td><td>{r.registration_status}</td></tr>)}</tbody></table></div>}</section>
 </>}</PortalFrame>;
}

export default function App(){
  const [page,setPage]=useState('Overview');
  const [user,setUser]=useState<AuthUser|null>(null);
  const [authLoading,setAuthLoading]=useState(true);
  const [authError,setAuthError]=useState('');
  const [loginUsername,setLoginUsername]=useState('');
  const [loginPassword,setLoginPassword]=useState('');
  const [loginError,setLoginError]=useState('');
  const [authMode,setAuthMode]=useState<'welcome'|'signin'|'create'>('welcome');
  const [signupRole,setSignupRole]=useState<'Student'|'Lecturer'>('Student');
  const [studentSignupPath,setStudentSignupPath]=useState<'existing'|'applicant'>('existing');
  const [publicDepartments,setPublicDepartments]=useState<{id:number;name:string;faculty_name:string}[]>([]);
  const [authNotice,setAuthNotice]=useState('');
  const [mobileNavOpen,setMobileNavOpen]=useState(false);
  const [dashboard,setDashboard]=useState<Dashboard|null>(null);
  const [students,setStudents]=useState<Student[]>([]);
  const [departments,setDepartments]=useState<Department[]>([]);
  const [faculties,setFaculties]=useState<Faculty[]>([]);
  const [gradeSubmissions,setGradeSubmissions]=useState<GradeSubmission[]>([]);
  const [courses,setCourses]=useState<Course[]>([]);
  const [lecturers,setLecturers]=useState<Lecturer[]>([]);
  const [academicSessions,setAcademicSessions]=useState<AcademicSession[]>([]);
  const [semesters,setSemesters]=useState<Semester[]>([]);
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
  const [courseForm,setCourseForm]=useState({department_id:'',course_code:'',title:'',credit_units:'3',level:'300'});
  const [lecturerForm,setLecturerForm]=useState({staff_number:'',first_name:'',last_name:'',department_id:'',username:'',password:''});
  const [sessionForm,setSessionForm]=useState({name:'2026/2027',starts_on:'',ends_on:'',is_current:true});
  const [semesterForm,setSemesterForm]=useState({academic_session_id:'',name:'First Semester',registration_opens_at:'',registration_closes_at:''});
  const [offeringForm,setOfferingForm]=useState({course_id:'',semester_id:'',lecturer_id:'',section:'A',capacity:'40'});
  const [accountForm,setAccountForm]=useState({role:'Student',record_id:'',username:'',password:''});

  async function refresh(){
    setLoading(true);setError('');
    try{
      const [d,s,de,fa,r,b,a,gs,cs,ls,as,ss]=await Promise.all([
        requestWithRetry<Dashboard>('/api/dashboard'),requestWithRetry<Student[]>('/api/students'),
        requestWithRetry<Department[]>('/api/departments'),requestWithRetry<Faculty[]>('/api/faculties'),requestWithRetry<Result[]>('/api/results'),
        requestWithRetry<Backup[]>('/api/backups'),requestWithRetry<ActivityItem[]>('/api/activity'),requestWithRetry<GradeSubmission[]>('/api/admin/grade-submissions'),requestWithRetry<Course[]>('/api/admin/courses'),requestWithRetry<Lecturer[]>('/api/admin/lecturers'),requestWithRetry<AcademicSession[]>('/api/admin/academic-sessions'),requestWithRetry<Semester[]>('/api/admin/semesters'),
      ]);
      setDashboard(d);setStudents(s);setDepartments(de);setFaculties(fa);setResults(r);setBackups(b);setActivity(a);setGradeSubmissions(gs);setCourses(cs);setLecturers(ls);setAcademicSessions(as);setSemesters(ss);
    }catch(e){setError(e instanceof Error?e.message:'Could not connect to the API.');}
    finally{setLoading(false);}
  }
  async function checkSession(){setAuthLoading(true);setAuthError('');try{setUser(await requestWithRetry<AuthUser>('/api/auth/me'));}catch(e){if(e instanceof ApiError&&e.status===401){setUser(null);}else{setAuthError(e instanceof Error?e.message:'CampusBook could not connect.');}}finally{setAuthLoading(false);}}
  useEffect(()=>{void checkSession();},[]);
  useEffect(()=>{if(authMode==='create'){requestWithRetry<{id:number;name:string;faculty_name:string}[]>('/api/public/departments',3).then(setPublicDepartments).catch(()=>setPublicDepartments([]));}},[authMode]);
  useEffect(()=>{if(user?.role==='Administrator')void refresh();},[user]);
  useEffect(()=>{if(!notice)return;const t=window.setTimeout(()=>setNotice(''),4000);return()=>window.clearTimeout(t);},[notice]);

  async function submitLogin(e:FormEvent){e.preventDefault();setLoginError('');try{const account=await requestWithRetry<AuthUser>('/api/auth/login',4,{method:'POST',body:JSON.stringify({username:loginUsername,password:loginPassword})});setUser(account);setLoginPassword('');}catch(e){setLoginError(e instanceof Error?e.message:'Unable to sign in.');}}
  async function quickDemoLogin(role:'Administrator'|'Lecturer'|'Student'|'ExamsOfficer'){setLoginError('');try{const account=role==='Administrator'?await requestWithRetry<AuthUser>('/api/auth/demo-admin',4,{method:'POST'}):await requestWithRetry<AuthUser>('/api/auth/demo-login',4,{method:'POST',body:JSON.stringify({role})});setUser(account);setLoginPassword('');}catch(e){setLoginError(e instanceof Error?e.message:'Unable to open the demo account.');}}
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

  async function createCourse(e:FormEvent){e.preventDefault();setSaving(true);try{await request('/api/admin/courses',{method:'POST',body:JSON.stringify({...courseForm,department_id:Number(courseForm.department_id),credit_units:Number(courseForm.credit_units)})});setCourseForm({department_id:'',course_code:'',title:'',credit_units:'3',level:'300'});setNotice('Course added to catalogue.');await refresh();}catch(e){setNotice(e instanceof Error?e.message:'Could not create course.');}finally{setSaving(false);}}
  async function createLecturer(e:FormEvent){e.preventDefault();setSaving(true);try{const lecturer=await request<Lecturer>('/api/admin/lecturers',{method:'POST',body:JSON.stringify({staff_number:lecturerForm.staff_number,first_name:lecturerForm.first_name,last_name:lecturerForm.last_name,department_id:Number(lecturerForm.department_id)})});await request('/api/admin/accounts',{method:'POST',body:JSON.stringify({username:lecturerForm.username,password:lecturerForm.password,role:'Lecturer',lecturer_id:lecturer.id})});setLecturerForm({staff_number:'',first_name:'',last_name:'',department_id:'',username:'',password:''});setNotice('Lecturer record and sign-in account created.');await refresh();}catch(e){setNotice(e instanceof Error?e.message:'Lecturer setup failed. Check whether the lecturer record was created before retrying.');}finally{setSaving(false);}}
  async function createSession(e:FormEvent){e.preventDefault();setSaving(true);try{await request('/api/admin/academic-sessions',{method:'POST',body:JSON.stringify({name:sessionForm.name,starts_on:sessionForm.starts_on||null,ends_on:sessionForm.ends_on||null,is_current:sessionForm.is_current})});setNotice('Academic session created.');await refresh();}catch(e){setNotice(e instanceof Error?e.message:'Could not create academic session.');}finally{setSaving(false);}}
  async function createSemester(e:FormEvent){e.preventDefault();setSaving(true);try{await request('/api/admin/semesters',{method:'POST',body:JSON.stringify({academic_session_id:Number(semesterForm.academic_session_id),name:semesterForm.name,registration_opens_at:semesterForm.registration_opens_at?new Date(semesterForm.registration_opens_at).toISOString():null,registration_closes_at:semesterForm.registration_closes_at?new Date(semesterForm.registration_closes_at).toISOString():null,is_published:true})});setNotice('Semester created.');await refresh();}catch(e){setNotice(e instanceof Error?e.message:'Could not create semester.');}finally{setSaving(false);}}
  async function createOffering(e:FormEvent){e.preventDefault();setSaving(true);try{await request('/api/admin/course-offerings',{method:'POST',body:JSON.stringify({course_id:Number(offeringForm.course_id),semester_id:Number(offeringForm.semester_id),lecturer_id:Number(offeringForm.lecturer_id),section:offeringForm.section,capacity:offeringForm.capacity?Number(offeringForm.capacity):null})});setNotice('Course offering opened for registration.');setOfferingForm({course_id:'',semester_id:'',lecturer_id:'',section:'A',capacity:'40'});await refresh();}catch(e){setNotice(e instanceof Error?e.message:'Could not create course offering.');}finally{setSaving(false);}}
  async function provisionStudent(e:FormEvent){e.preventDefault();setSaving(true);try{await request('/api/admin/accounts',{method:'POST',body:JSON.stringify({username:accountForm.username,password:accountForm.password,role:'Student',student_id:Number(accountForm.record_id)})});setAccountForm({role:'Student',record_id:'',username:'',password:''});setNotice('Student sign-in account created.');}catch(e){setNotice(e instanceof Error?e.message:'Could not create student account.');}finally{setSaving(false);}}
  async function approveGrades(id:number){try{await request('/api/admin/offerings/'+id+'/approve',{method:'POST'});setNotice('Submitted grades approved and published.');await refresh();}catch(e){setNotice(e instanceof Error?e.message:'Could not approve grades.');}}
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

  const nav=[{label:'Overview',icon:LayoutDashboard},{label:'Students',icon:Users},{label:'Departments',icon:Building2},{label:'Academic Setup',icon:BookOpen},{label:'Results',icon:BookOpen},{label:'Backup & Recovery',icon:Database},{label:'Activity Log',icon:Activity}];
  if(authError)return <div className="auth-screen"><div className="auth-card"><div className="portal-brand"><div className="brand-mark"><GraduationCap size={21}/></div><span>campus<span className="brand-light">book</span></span></div><h1>Connecting to CampusBook</h1><p className="auth-description">{authError}</p><p className="auth-description">The service may be waking up. CampusBook already tried reconnecting automatically.</p><button className="primary-button" onClick={()=>void checkSession()}>Try again</button></div></div>;
  if(authLoading)return <div className="auth-screen"><div className="auth-card"><div className="portal-brand"><div className="brand-mark"><GraduationCap size={21}/></div><span>campus<span className="brand-light">book</span></span></div><p>Checking your session…</p></div></div>;
  if(!user)return <div className="auth-screen"><div className="auth-card auth-card-home"><div className="portal-brand"><div className="brand-mark"><GraduationCap size={21}/></div><span>campus<span className="brand-light">book</span></span></div><p className="eyebrow">RIVERS STATE UNIVERSITY · ACADEMIC RECORDS</p>{loginError&&<div className="portal-error">{loginError}</div>}
    {authMode==='welcome'&&<><h1>Welcome to CampusBook</h1><p className="auth-description">Choose a demo workspace or continue with your institution account.</p><div className="demo-access demo-access-primary"><span>Quick access · no account setup needed</span><button type="button" onClick={()=>void quickDemoLogin('Administrator')}>Demo administrator</button><button type="button" onClick={()=>void quickDemoLogin('Student')}>Demo student</button><button type="button" onClick={()=>void quickDemoLogin('Lecturer')}>Demo lecturer</button><button type="button" onClick={()=>void quickDemoLogin('ExamsOfficer')}>Demo examination officer</button></div><div className="auth-switch-links"><button type="button" onClick={()=>{setAuthMode('signin');setLoginError('');}}>Sign in</button><span>or</span><button type="button" onClick={()=>{setAuthMode('create');setLoginError('');}}>Create one</button></div></>}
    {authMode==='signin'&&<><h1>Sign in</h1><p className="auth-description">Use your institution-issued account details.</p><form className="auth-page-form" onSubmit={submitLogin}><label>Email or username<input autoComplete="username" value={loginUsername} onChange={e=>setLoginUsername(e.target.value)} required/></label><label>Password<input type="password" autoComplete="current-password" value={loginPassword} onChange={e=>setLoginPassword(e.target.value)} required/></label><button className="primary-button" type="submit">Sign in</button></form><div className="auth-switch-links"><button type="button" onClick={()=>setAuthMode('create')}>Create one</button><span>·</span><button type="button" onClick={()=>setAuthMode('welcome')}>Back to demo access</button></div></>}
    {authNotice&&<div className="portal-notice">{authNotice}</div>}
    {authMode==='create'&&<><h1>Create account</h1><p className="auth-description">Students can activate an existing university record or apply before their matriculation number is issued.</p><form className="auth-page-form" onSubmit={async e=>{e.preventDefault();setLoginError('');setAuthNotice('');const form=e.currentTarget;const data=new FormData(form);const email=String(data.get('email')).trim().toLowerCase();try{if(signupRole==='Student'&&studentSignupPath==='applicant'){await request('/api/auth/apply',{method:'POST',body:JSON.stringify({email,password:String(data.get('password')),first_name:String(data.get('first_name')),last_name:String(data.get('last_name')),department_id:Number(data.get('department_id')),application_reference:String(data.get('application_reference')||'')||null})});setLoginUsername(email);setLoginPassword('');setAuthNotice('Application submitted. Your account will remain pending until the institution verifies your admission and assigns your official matriculation number. You cannot access student records yet.');setAuthMode('signin');}else{const account=await request<AuthUser>('/api/auth/signup',{method:'POST',body:JSON.stringify({email,password:String(data.get('password')),role:signupRole,identity_number:String(data.get('identity_number'))})});setUser(account);}}catch(err){setLoginError(err instanceof Error?err.message:'Could not create your account.');}}}>
      <label>Account type<select value={signupRole} onChange={e=>setSignupRole(e.target.value as 'Student'|'Lecturer')}><option value="Student">Student</option><option value="Lecturer">Lecturer</option></select></label>
      {signupRole==='Student'&&<label>Student registration<select value={studentSignupPath} onChange={e=>setStudentSignupPath(e.target.value as 'existing'|'applicant')}><option value="existing">I have an official matriculation number</option><option value="applicant">I am a new applicant (no matric number yet)</option></select></label>}
      <label>Institutional email<input name="email" type="email" autoComplete="email" required/></label>
      {signupRole==='Student'&&studentSignupPath==='applicant'?<>
        <label>First name<input name="first_name" autoComplete="given-name" required/></label>
        <label>Last name<input name="last_name" autoComplete="family-name" required/></label>
        <label>Intended department<select name="department_id" required defaultValue=""><option value="" disabled>Select department</option>{publicDepartments.map(d=><option key={d.id} value={d.id}>{d.name} · {d.faculty_name}</option>)}</select></label>
        <label>Admission/application reference <span>(optional)</span><input name="application_reference" placeholder="Your application or admission reference"/></label>
        {!publicDepartments.length&&<p className="auth-description">Department choices are unavailable right now. Please try again later.</p>}
      </>:<label>{signupRole==='Student'?'Matriculation number':'Staff number'}<input name="identity_number" required placeholder="Institution-issued number"/></label>}
      <label>Create password<input name="password" type="password" minLength={8} autoComplete="new-password" required/></label>
      <p className="auth-description">{signupRole==='Student'&&studentSignupPath==='applicant'?'Submitting an application does not create an enrolled-student account. An administrator must verify admission and assign your real matriculation number first.':'Your existing student or lecturer record must already exist in CampusBook. Administrator accounts are provisioned by the institution.'}</p>
      <button className="primary-button" type="submit" disabled={signupRole==='Student'&&studentSignupPath==='applicant'&&!publicDepartments.length}>{signupRole==='Student'&&studentSignupPath==='applicant'?'Submit admission application':'Create account'}</button>
    </form><div className="auth-switch-links"><button type="button" onClick={()=>setAuthMode('signin')}>Sign in</button><span>·</span><button type="button" onClick={()=>setAuthMode('welcome')}>Back to demo access</button></div></>}
  </div></div>;
  if(user.role==='Administrator'&&loading&&!dashboard)return <div className="auth-screen"><div className="auth-card"><div className="portal-brand"><div className="brand-mark"><GraduationCap size={21}/></div><span>campus<span className="brand-light">book</span></span></div><h1>Loading CampusBook</h1><p className="auth-description">Connecting to the records service. If it has been idle, it may need a moment to wake up.</p></div></div>;
  if(user.role==='Administrator'&&error&&!dashboard)return <div className="auth-screen"><div className="auth-card"><div className="portal-brand"><div className="brand-mark"><GraduationCap size={21}/></div><span>campus<span className="brand-light">book</span></span></div><h1>Records service unavailable</h1><p className="auth-description">{error}</p><p className="auth-description">CampusBook has not replaced your records with zeroes. It will show the dashboard once it can retrieve the data.</p><button className="primary-button" onClick={()=>void refresh()}>Reconnect</button></div></div>;
  if(user.role==='Student')return <StudentPortal user={user} onLogout={()=>void signOut()}/>;
  if(user.role==='Lecturer')return <LecturerPortal user={user} onLogout={()=>void signOut()}/>;
  if(user.role==='ExamsOfficer')return <ExamsOfficerPortal user={user} onLogout={()=>void signOut()}/>;
  return <AdminWorkspace user={user} onLogout={()=>void signOut()}/>;
}

function grade(score:number){return score>=70?'A':score>=60?'B':score>=50?'C':score>=45?'D':score>=40?'E':'F';}
function PageHeading({eyebrow,title,description,action}:{eyebrow:string;title:string;description:string;action?:ReactNode}){return <div className="page-heading"><div><div className="eyebrow">{eyebrow}</div><h1>{title}</h1><p>{description}</p></div>{action}</div>;}
function Stat({icon:Icon,label,value,note,tone}:{icon:any;label:string;value:any;note:string;tone:string}){return <div className="stat-card"><div className={'stat-icon '+tone}><Icon size={19}/></div><div className="stat-label">{label}</div><div className="stat-value">{value}</div><div className="stat-note">{note}</div></div>;}
function PanelHead({title,subtitle,action}:{title:string;subtitle:string;action?:ReactNode}){return <div className="panel-head"><div><h2>{title}</h2><p>{subtitle}</p></div>{action}</div>;}
function StudentTable({rows,onEdit,onDelete}:{rows:Student[];onEdit:(s:Student)=>void;onDelete:(s:Student)=>void}){return <div className="table-wrap"><table><thead><tr><th>STUDENT</th><th>MATRIC NUMBER</th><th>FACULTY</th><th>DEPARTMENT</th><th>LEVEL</th><th>STATUS</th><th></th></tr></thead><tbody>{rows.map(s=><tr key={s.id}><td><div className="student-cell"><div className="student-avatar">{initials(s)}</div><div><b>{s.first_name} {s.last_name}</b></div></div></td><td className="mono">{s.matric_number}</td><td>{s.faculty}</td><td>{s.department}</td><td>{s.level} Level</td><td><span className={'status '+(s.status==='Active'?'status-active':'status-inactive')}><i/>{s.status}</span></td><td><div className="row-actions"><button className="row-action" title="Edit student" onClick={()=>onEdit(s)}><Pencil size={14}/></button><button className="row-action danger-action" title="Delete student" onClick={()=>void onDelete(s)}><Trash2 size={14}/></button></div></td></tr>)}</tbody></table>{!rows.length&&<Empty icon={Users} title="No student records" detail="Add a student to get started."/>}</div>;}
function ActivityList({rows}:{rows:ActivityItem[]}){return rows.length?<div className="activity-list">{rows.map(a=><div className="activity-row" key={a.id}><div className="activity-icon"><Activity size={15}/></div><div><b>{a.action}</b><span>{a.details}</span><small>{dateLabel(a.created_at)}</small></div></div>)}</div>:<Empty icon={Activity} title="No activity yet" detail="System events will appear here as you work."/>;}
function Empty({icon:Icon,title,detail}:{icon:any;title:string;detail:string}){return <div className="empty-state"><div><Icon size={22}/></div><b>{title}</b><span>{detail}</span></div>;}
function Modal({children,onClose,eyebrow,title,description}:{children:ReactNode;onClose:()=>void;eyebrow:string;title:string;description:string}){return <div className="modal-backdrop" onClick={onClose}><section className="modal" onClick={e=>e.stopPropagation()}><div className="modal-head"><div><div className="eyebrow">{eyebrow}</div><h2>{title}</h2><p>{description}</p></div><button type="button" className="icon-button" onClick={onClose}><X size={18}/></button></div>{children}</section></div>;}
function ModalActions({onCancel,saving,submit}:{onCancel:()=>void;saving:boolean;submit:string}){return <div className="modal-actions"><button type="button" className="secondary-button" onClick={onCancel}>Cancel</button><button className="primary-button" disabled={saving}>{saving?'Saving…':submit}</button></div>;}

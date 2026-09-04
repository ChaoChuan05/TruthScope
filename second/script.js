const input = document.getElementById('claimInput');
  const charcount = document.getElementById('charcount');
  input.addEventListener('input', () => {
    const len = input.value.length;
    charcount.textContent = Math.min(len,800) + ' / 800';
  });

  const examples = {
    'ai-edu': 'https://news.example.my/article — "Menteri X: AI akan jadi subjek wajib di semua sekolah menjelang 2027"',
    'fuel': '"Kerajaan akan hapus subsidi minyak sepenuhnya bulan depan" — viral WhatsApp forward, unverified source',
    'quote': 'Clip circulating on X claims an MP said healthcare would be privatised — full Hansard context missing'
  };
  document.querySelectorAll('.chip').forEach(chip=>{
    chip.addEventListener('click', ()=>{
      input.value = examples[chip.dataset.ex];
      input.dispatchEvent(new Event('input'));
      input.focus();
    });
  });

const results = document.getElementById('results');
const btn = document.getElementById('checkBtn');
const sealConic = document.getElementById('sealConic');
const scoreNum = document.getElementById('scoreNum');
const checkTime = document.getElementById('checkTime');

const verificationLoading =
  document.getElementById('verificationLoading');

const loadingStatus =
  document.getElementById('loadingStatus');
function scoreColor(score){
  if(score >= 75) return 'var(--signal)';   // teal — likely true
  if(score >= 45) return 'var(--amber)';    // amber — mixed
  return 'var(--noise)';                    // red — likely false
}

function animateScore(target){
  const color = scoreColor(target);
  sealConic.style.background =
    `conic-gradient(${color} 0% ${target}%, rgba(232,237,243,0.08) ${target}% 100%)`;


    let cur = 0;
    const step = () => {
      cur += Math.max(1, Math.round((target-cur)/8));
      if(cur >= target){ cur = target; scoreNum.textContent = cur; return; }
      scoreNum.textContent = cur;
      requestAnimationFrame(()=>setTimeout(step,16));
    };
    step();
  }

function runCheck(){

  btn.disabled = true;

  const original = btn.innerHTML;

  // Show button loading state
  btn.innerHTML =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" style="animation:spin 0.9s linear infinite"><circle cx="12" cy="12" r="9" stroke-dasharray="40" stroke-dashoffset="10"/></svg> Analyzing…';

  // Show verification loading panel
  verificationLoading.classList.add('active');

  const statuses = [
    'Connecting to verification engine',
    'Analyzing claim',
    'Checking available evidence',
    'Comparing information',
    'Running AI verification',
    'Preparing verification result'
  ];

  let statusIndex = 0;

  const statusInterval = setInterval(() => {

    statusIndex++;

    if(statusIndex < statuses.length){

      loadingStatus.style.opacity = '0';

      setTimeout(() => {
        loadingStatus.textContent = statuses[statusIndex];
        loadingStatus.style.opacity = '1';
      }, 200);

    }

  }, 1800);


  // Current time
  const now = new Date();

  const fmt =
    now.getFullYear() + '-' +
    String(now.getMonth()+1).padStart(2,'0') + '-' +
    String(now.getDate()).padStart(2,'0') + ' ' +
    String(now.getHours()).padStart(2,'0') + ':' +
    String(now.getMinutes()).padStart(2,'0') +
    ' MYT';


  /*
   * =====================================
   * YOUR BACKEND REQUEST WILL GO HERE
   * =====================================
   *
   * For now, your demo waits 8 seconds.
   */


  setTimeout(() => {

    clearInterval(statusInterval);

    // Hide loading panel
    verificationLoading.classList.remove('active');

    // Restore button
    btn.innerHTML = original;
    btn.disabled = false;

    // Update result
    checkTime.textContent = fmt;

    results.classList.add('show');

    animateScore(72);

    results.scrollIntoView({
      behavior:'smooth',
      block:'start'
    });

  }, 8000);
}

  btn.addEventListener('click', runCheck);

  const style = document.createElement('style');
  style.textContent = '@keyframes spin{to{transform:rotate(360deg)}}';
  document.head.appendChild(style);


 
// LOGIN MODAL


const loginBtn = document.getElementById("loginBtn");
const loginModal = document.getElementById("loginModal");
const loginClose = document.getElementById("loginClose");
const loginForm = document.getElementById("loginForm");
const loginMessage = document.getElementById("loginMessage");


// Open Login Modal
loginBtn.addEventListener("click", function () {
    loginModal.classList.add("active");
});


// Close Login Modal
loginClose.addEventListener("click", function () {
    loginModal.classList.remove("active");
});


// Close when clicking outside the login box
loginModal.addEventListener("click", function (event) {

    if (event.target === loginModal) {
        loginModal.classList.remove("active");
    }

});


// Login Form
loginForm.addEventListener("submit", function (event) {

    event.preventDefault();

    const username = document.getElementById("username").value.trim();
    const password = document.getElementById("password").value;

    // Demo username and password
    if (username === "admin" && password === "123456") {

        loginMessage.textContent = "Login successful!";
        loginMessage.style.color = "var(--signal)";


    } else {

        loginMessage.textContent = "Invalid username or password.";
        loginMessage.style.color = "var(--noise)";

    }

});



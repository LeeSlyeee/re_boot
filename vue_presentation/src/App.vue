<template>
  <div 
    class="relative w-screen h-screen flex flex-col items-center justify-center outline-none bg-slate-900 overflow-hidden"
    tabindex="0"
    @keydown.right="nextSlide"
    @keydown.left="prevSlide"
    @keydown.space.prevent="nextSlide"
    ref="container"
  >
    <!-- Background Decoration -->
    <div class="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] bg-blue-600 rounded-full mix-blend-multiply filter blur-[128px] opacity-30 animate-blob"></div>
    <div class="absolute top-[-10%] right-[-10%] w-[40%] h-[40%] bg-teal-500 rounded-full mix-blend-multiply filter blur-[128px] opacity-30 animate-blob animation-delay-2000"></div>
    <div class="absolute bottom-[-20%] left-[20%] w-[40%] h-[40%] bg-emerald-500 rounded-full mix-blend-multiply filter blur-[128px] opacity-30 animate-blob animation-delay-4000"></div>

    <!-- Progress Bar -->
    <div class="absolute top-0 left-0 h-1.5 bg-gradient-to-r from-blue-500 to-teal-400 transition-all duration-500 ease-out z-50" :style="{ width: progress + '%' }"></div>
    
    <!-- Slide Counter -->
    <div class="absolute bottom-6 right-8 text-slate-400 font-mono text-lg z-50">
      {{ currentSlide + 1 }} <span class="opacity-50">/</span> {{ totalSlides }}
    </div>

    <!-- Navigation Hints -->
    <div class="absolute bottom-6 left-8 text-slate-500 text-sm font-semibold tracking-widest flex gap-6 z-50">
      <button @click="prevSlide" class="hover:text-blue-400 transition-colors uppercase cursor-pointer">&larr; Prev</button>
      <button @click="nextSlide" class="hover:text-teal-400 transition-colors uppercase cursor-pointer">Next &rarr;</button>
    </div>

    <!-- Slide Content Area -->
    <div class="slide-wrapper w-full max-w-6xl h-[80%] p-10 flex flex-col justify-center relative z-10">
      <transition name="slide-fade" mode="out-in">
        
        <!-- 1. 팀 소개 -->
        <section v-if="currentSlide === 0" class="w-full text-center flex flex-col items-center">
          <div class="inline-block px-6 py-2 mb-8 rounded-full border border-blue-500/30 bg-blue-500/10 text-blue-300 font-bold tracking-widest text-sm">FINAL PRESENTATION</div>
          <h1 class="text-7xl font-extrabold mb-8 text-transparent bg-clip-text bg-gradient-to-r from-blue-400 via-cyan-400 to-teal-400">Re:Boot</h1>
          <h2 class="text-4xl text-slate-200 mb-16 font-semibold">AI 기반 실시간 학습 경험 자산화 플랫폼</h2>
          
          <div class="bg-slate-800/80 backdrop-blur-md rounded-3xl p-10 border border-slate-700/50 shadow-2xl max-w-2xl w-full mx-auto transform transition hover:scale-105">
            <h3 class="text-2xl text-teal-400 font-bold mb-6">4조 팀 소개</h3>
            <div class="flex items-center justify-center gap-6">
              <div class="w-20 h-20 bg-gradient-to-br from-blue-500 to-teal-500 rounded-full flex items-center justify-center text-2xl font-bold text-white shadow-lg">HJ</div>
              <div class="text-left">
                <p class="text-slate-100 text-2xl font-bold">김혜진</p>
                <p class="text-slate-400 text-lg mt-1">기획 & 풀스택 개발</p>
              </div>
            </div>
            <div class="mt-8 pt-6 border-t border-slate-700/50">
              <p class="text-slate-300 text-lg leading-relaxed">단 4주, 교육의 페인포인트를 해결하기 위해 치열하게 몰입한 과정과 결과를 발표합니다.</p>
            </div>
          </div>
        </section>

        <!-- 2. Re:Boot 소개 -->
        <section v-else-if="currentSlide === 1" class="w-full">
          <div class="flex items-center gap-4 mb-4">
            <span class="text-blue-500 text-2xl">💡</span>
            <h2 class="text-2xl font-bold text-blue-400 tracking-wider">INTRODUCTION</h2>
          </div>
          <h3 class="text-5xl font-bold text-white mb-12">Re:Boot를 소개합니다</h3>
          
          <div class="grid grid-cols-3 gap-8 h-full">
            <!-- Pain Point -->
            <div class="bg-slate-800/60 backdrop-blur border-t-4 border-t-red-500 rounded-2xl p-8 shadow-xl">
              <div class="text-4xl mb-6">🎯</div>
              <h4 class="text-2xl font-bold text-red-400 mb-6">Pain Point</h4>
              <ul class="space-y-4 text-slate-300 text-lg">
                <li class="flex items-start"><span class="mr-3 text-red-500 mt-1">✕</span> 보이지 않는 격차</li>
                <li class="flex items-start"><span class="mr-3 text-red-500 mt-1">✕</span> 필기의 역설 (집중 분산)</li>
                <li class="flex items-start"><span class="mr-3 text-red-500 mt-1">✕</span> 중도 포기 = All or Nothing</li>
              </ul>
            </div>
            
            <!-- Solution -->
            <div class="bg-slate-800/60 backdrop-blur border-t-4 border-t-blue-500 rounded-2xl p-8 shadow-xl">
              <div class="text-4xl mb-6">✨</div>
              <h4 class="text-2xl font-bold text-blue-400 mb-6">Solution</h4>
              <ul class="space-y-4 text-slate-300 text-lg">
                <li class="flex items-start"><span class="mr-3 text-blue-500 mt-1">✓</span> 실시간 AI 학습 비서 (STT)</li>
                <li class="flex items-start"><span class="mr-3 text-blue-500 mt-1">✓</span> 데이터 기반 적응형 학습</li>
                <li class="flex items-start"><span class="mr-3 text-blue-500 mt-1">✓</span> 학습 경험의 자산화 (스킬블록)</li>
              </ul>
            </div>
            
            <!-- Core Value -->
            <div class="bg-gradient-to-b from-teal-900/40 to-slate-800/60 backdrop-blur border border-teal-500/30 rounded-2xl p-8 shadow-xl flex flex-col justify-center relative overflow-hidden">
              <div class="absolute top-0 right-0 w-32 h-32 bg-teal-500/10 rounded-full blur-2xl"></div>
              <h4 class="text-2xl font-bold text-teal-400 mb-8 z-10">Core Value</h4>
              <p class="text-slate-200 leading-relaxed text-xl z-10 italic">
                <span class="opacity-50 line-through block mb-2 font-light">"무엇을 가르칠 것인가?"</span>
                <span class="text-3xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-teal-400 to-blue-400 block mt-4">
                  "어떻게 끝까지<br>완주시킬 것인가"
                </span>
              </p>
            </div>
          </div>
        </section>

        <!-- 3. 4주간의 개발 과정 -->
        <section v-else-if="currentSlide === 2" class="w-full">
          <div class="flex items-center gap-4 mb-4">
            <span class="text-teal-500 text-2xl">⏱️</span>
            <h2 class="text-2xl font-bold text-teal-400 tracking-wider">TIMELINE</h2>
          </div>
          <h3 class="text-5xl font-bold text-white mb-16">4주간의 개발 과정</h3>
          
          <div class="relative flex justify-between w-full pt-8">
            <!-- 트랙 선 -->
            <div class="absolute top-14 left-0 right-0 h-1 bg-slate-700"></div>
            <!-- 그라데이션 진행 선 -->
            <div class="absolute top-14 left-0 w-full h-1 bg-gradient-to-r from-blue-500 to-teal-400 shadow-[0_0_10px_rgba(45,212,191,0.5)]"></div>

            <div v-for="(week, index) in [
              { title: '기획 & 설계', desc: ['User Journey 매핑', 'Figma UI/UX', 'ERD 설계'] },
              { title: '핵심 백엔드 & AI', desc: ['Django API', 'STT 엔진', 'GPT-4o 파이프라인'] },
              { title: '프론트엔드 연동', desc: ['Vue.js + Tailwind', '웹앱/대시보드 분리', 'Chart.js 시각화'] },
              { title: '통합 & 배포 최적화', desc: ['OCI Nginx 셋업', '네트워크 예외 처리', '최종 디버깅'] }
            ]" :key="index" class="relative z-10 flex flex-col items-center w-1/4 px-4">
              <div class="w-14 h-14 rounded-full bg-slate-900 border-4 border-teal-400 flex items-center justify-center text-xl font-bold text-white shadow-[0_0_15px_rgba(45,212,191,0.3)] mb-6">
                {{ index + 1 }}
              </div>
              <div class="bg-slate-800/80 backdrop-blur rounded-xl p-5 border border-slate-700 shadow-lg w-full transform transition hover:-translate-y-2">
                <h4 class="text-lg font-bold text-teal-300 mb-3 text-center">{{ index + 1 }}주차: {{ week.title }}</h4>
                <ul class="text-sm text-slate-300 space-y-2">
                  <li v-for="(item, i) in week.desc" :key="i" class="flex items-center">
                    <span class="w-1.5 h-1.5 bg-blue-500 rounded-full mr-2"></span>
                    {{ item }}
                  </li>
                </ul>
              </div>
            </div>
          </div>
        </section>

        <!-- 4. Service Flow -->
        <section v-else-if="currentSlide === 3" class="w-full">
          <div class="flex items-center gap-4 mb-4">
            <span class="text-indigo-400 text-2xl">🔄</span>
            <h2 class="text-2xl font-bold text-indigo-400 tracking-wider">SERVICE FLOW</h2>
          </div>
          <h3 class="text-5xl font-bold text-white mb-12">핵심 서비스 흐름</h3>
          
          <div class="flex gap-8">
            <!-- Student Flow -->
            <div class="flex-1 bg-indigo-900/20 border border-indigo-500/30 p-8 rounded-3xl backdrop-blur-sm relative">
              <div class="absolute -top-6 left-1/2 -translate-x-1/2 bg-slate-900 border-2 border-indigo-500 rounded-full px-6 py-3 flex items-center gap-3">
                <span class="text-2xl">🧑‍🎓</span>
                <span class="text-xl font-bold text-indigo-300">학생 (Student)</span>
              </div>
              
              <div class="mt-8 space-y-4">
                <div class="bg-indigo-800/40 p-5 rounded-xl border border-indigo-500/20 flex items-center gap-4">
                  <div class="w-8 h-8 rounded-full bg-indigo-500 flex items-center justify-center font-bold">1</div>
                  <span class="text-lg text-slate-200">수준 진단 (Placement Test)</span>
                </div>
                <div class="flex justify-center text-indigo-500">▼</div>
                <div class="bg-indigo-800/40 p-5 rounded-xl border border-indigo-500/20 flex items-center gap-4">
                  <div class="w-8 h-8 rounded-full bg-indigo-500 flex items-center justify-center font-bold">2</div>
                  <span class="text-lg text-slate-200">라이브 세션 참여 (STT & 이해도 펄스)</span>
                </div>
                <div class="flex justify-center text-indigo-500">▼</div>
                <div class="bg-indigo-800/40 p-5 rounded-xl border border-indigo-500/20 flex items-center gap-4">
                  <div class="w-8 h-8 rounded-full bg-indigo-500 flex items-center justify-center font-bold">3</div>
                  <span class="text-lg text-slate-200">AI 통합 노트 & 자동 생성 퀴즈</span>
                </div>
                <div class="flex justify-center text-indigo-500">▼</div>
                <div class="bg-indigo-800/40 p-5 rounded-xl border border-indigo-500/20 flex items-center gap-4">
                  <div class="w-8 h-8 rounded-full bg-indigo-500 flex items-center justify-center font-bold">4</div>
                  <span class="text-lg text-slate-200">스킬블록 자산화 & 복습 라우팅</span>
                </div>
              </div>
            </div>

            <!-- Instructor Flow -->
            <div class="flex-1 bg-teal-900/20 border border-teal-500/30 p-8 rounded-3xl backdrop-blur-sm relative">
              <div class="absolute -top-6 left-1/2 -translate-x-1/2 bg-slate-900 border-2 border-teal-500 rounded-full px-6 py-3 flex items-center gap-3">
                <span class="text-2xl">👨‍🏫</span>
                <span class="text-xl font-bold text-teal-300">교수자 (Instructor)</span>
              </div>
              
              <div class="mt-8 space-y-4">
                <div class="bg-teal-800/40 p-5 rounded-xl border border-teal-500/20 flex items-center gap-4">
                  <div class="w-8 h-8 rounded-full bg-teal-500 flex items-center justify-center font-bold">1</div>
                  <span class="text-lg text-slate-200">데이터 통합 모니터링 (진도/출석)</span>
                </div>
                <div class="flex justify-center text-teal-500">▼</div>
                <div class="bg-teal-800/40 p-5 rounded-xl border border-teal-500/20 flex items-center gap-4">
                  <div class="w-8 h-8 rounded-full bg-teal-500 flex items-center justify-center font-bold">2</div>
                  <span class="text-lg text-slate-200">예측 AI 기반 위험군 학생 탐지</span>
                </div>
                <div class="flex justify-center text-teal-500">▼</div>
                <div class="bg-teal-800/40 p-5 rounded-xl border border-teal-500/20 flex items-center gap-4">
                  <div class="w-8 h-8 rounded-full bg-teal-500 flex items-center justify-center font-bold">3</div>
                  <span class="text-lg text-slate-200">AI 튜터링 제안 검토 (HITL)</span>
                </div>
                <div class="flex justify-center text-teal-500">▼</div>
                <div class="bg-teal-800/40 p-5 rounded-xl border border-teal-500/20 flex items-center gap-4">
                  <div class="w-8 h-8 rounded-full bg-teal-500 flex items-center justify-center font-bold">4</div>
                  <span class="text-lg text-slate-200">타겟 맞춤 보충 자료 및 메시지 발송</span>
                </div>
              </div>
            </div>
          </div>
        </section>

        <!-- 5. 라이브 데모 시나리오 -->
        <section v-else-if="currentSlide === 4" class="w-full text-center">
          <div class="flex items-center justify-center gap-4 mb-4">
            <span class="text-red-500 text-2xl">🔥</span>
            <h2 class="text-2xl font-bold text-red-400 tracking-wider">LIVE DEMO</h2>
          </div>
          <h3 class="text-5xl font-bold text-white mb-6">시연 영상</h3>
          <p class="text-xl text-slate-400 mb-10">실제 시스템이 어떻게 작동하는지 확인합니다.</p>
          
          <div class="max-w-4xl mx-auto aspect-video bg-slate-950 border border-slate-700/50 rounded-3xl flex flex-col items-center justify-center shadow-[0_0_30px_rgba(0,0,0,0.5)] relative overflow-hidden group cursor-pointer hover:border-red-500/50 transition-colors">
            <!-- Play Button UI Pattern -->
            <div class="w-24 h-24 bg-red-500/90 rounded-full flex items-center justify-center shadow-lg group-hover:scale-110 transition-transform">
              <svg class="w-10 h-10 text-white ml-2" fill="currentColor" viewBox="0 0 20 20"><path d="M4 4l12 6-12 6z"></path></svg>
            </div>
            <p class="absolute bottom-6 text-slate-500 text-sm tracking-widest">[ 영상 재생을 클릭하세요 ]</p>
          </div>
        </section>

        <!-- 6. 시스템 아키텍처 -->
        <section v-else-if="currentSlide === 5" class="w-full">
           <div class="flex items-center gap-4 mb-4">
            <span class="text-blue-500 text-2xl">🏗️</span>
            <h2 class="text-2xl font-bold text-blue-400 tracking-wider">ARCHITECTURE</h2>
          </div>
          <h3 class="text-5xl font-bold text-white mb-10">시스템 아키텍처</h3>
          
          <div class="bg-slate-800/50 backdrop-blur-md rounded-3xl p-10 border border-slate-700 shadow-2xl relative overflow-hidden">
            <!-- Connection Lines -->
            <div class="absolute left-1/2 top-0 bottom-0 w-px border-l-2 border-dashed border-slate-600"></div>

            <div class="grid grid-cols-2 gap-16 relative z-10">
              <!-- Left Column: Frontend -->
              <div class="space-y-8">
                <div class="bg-gradient-to-r from-blue-900/50 to-slate-800 p-6 rounded-2xl border border-blue-500/30">
                  <h4 class="text-xl font-bold text-blue-300 border-b border-blue-500/20 pb-3 mb-4">Client Layer</h4>
                  <div class="flex items-center gap-4 mb-4">
                    <img src="https://upload.wikimedia.org/wikipedia/commons/9/95/Vue.js_Logo_2.svg" class="w-10 h-10">
                    <div>
                      <p class="text-xl font-bold text-white">Vue.js 3 + Pinia</p>
                      <p class="text-sm text-blue-200">웹 앱 (1: 학생용 / 2: 교수용)</p>
                    </div>
                  </div>
                  <div class="inline-flex gap-2 mt-2">
                    <span class="px-3 py-1 bg-slate-700 rounded-md text-xs text-slate-300">TailwindCSS</span>
                    <span class="px-3 py-1 bg-slate-700 rounded-md text-xs text-slate-300">Chart.js</span>
                    <span class="px-3 py-1 bg-slate-700 rounded-md text-xs text-slate-300">Vite</span>
                  </div>
                </div>

                <div class="bg-slate-800 p-6 rounded-2xl border border-slate-600 text-center">
                  <div class="text-slate-400 text-sm mb-2 font-mono">HTTPS / OCI Cloud</div>
                  <h4 class="text-xl font-bold text-white">Nginx Web Server</h4>
                </div>
              </div>

              <!-- Right Column: Backend & AI -->
              <div class="space-y-8">
                <div class="bg-gradient-to-l from-green-900/50 to-slate-800 p-6 rounded-2xl border border-green-500/30">
                  <h4 class="text-xl font-bold text-green-300 border-b border-green-500/20 pb-3 mb-4">Server Layer</h4>
                  <div class="flex items-center gap-4 mb-4">
                    <div class="w-10 h-10 bg-green-800 rounded-md border border-green-500 flex items-center justify-center font-bold text-green-300">dj</div>
                    <div>
                      <p class="text-xl font-bold text-white">Django REST API</p>
                      <p class="text-sm text-green-200">Gunicorn / JWT Auth</p>
                    </div>
                  </div>
                </div>

                <div class="grid grid-cols-2 gap-4">
                  <div class="bg-slate-800 p-5 rounded-xl border border-yellow-500/30">
                     <h4 class="text-lg font-bold text-yellow-400 mb-2">Database</h4>
                     <p class="text-white font-semibold">PostgreSQL</p>
                     <p class="text-xs text-slate-400">pgvector (RAG)</p>
                  </div>
                  <div class="bg-slate-800 p-5 rounded-xl border border-purple-500/30">
                     <h4 class="text-lg font-bold text-purple-400 mb-2">AI Engine</h4>
                     <p class="text-white font-semibold">OpenAI GPT-4o</p>
                     <p class="text-xs text-slate-400">Whisper API</p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        <!-- 7. 기대 효과 및 비즈니스 임팩트 -->
        <section v-else-if="currentSlide === 6" class="w-full">
          <div class="flex items-center gap-4 mb-4">
            <span class="text-emerald-500 text-2xl">📈</span>
            <h2 class="text-2xl font-bold text-emerald-400 tracking-wider">BUSINESS IMPACT</h2>
          </div>
          <h3 class="text-5xl font-bold text-white mb-12">기대 효과 및 임팩트</h3>
          
          <div class="grid grid-cols-2 gap-10">
            <!-- B2B/B2G -->
            <div class="bg-slate-800 border-t-8 border-t-emerald-500 rounded-3xl p-8 hover:-translate-y-2 transition-transform duration-300">
              <div class="w-16 h-16 bg-emerald-500/20 rounded-2xl flex items-center justify-center text-3xl mb-6">🏢</div>
              <h4 class="text-3xl font-bold text-white mb-6">B2G / B2B<br><span class="text-emerald-400 text-xl">(교육기관)</span></h4>
              
              <div class="space-y-6">
                <div>
                  <h5 class="text-xl font-bold text-slate-200 mb-2 flex items-center"><span class="text-emerald-500 mr-2">↑</span> 수료율 및 유지율 상승</h5>
                  <p class="text-slate-400">조기 위험군 탐지를 통한 중도 이탈률 획기적 방어로 국비 지원 예산 낭비 최소화</p>
                </div>
                <div>
                  <h5 class="text-xl font-bold text-slate-200 mb-2 flex items-center"><span class="text-emerald-500 mr-2">↓</span> 교수자 업무 로드 30% 감소</h5>
                  <p class="text-slate-400">데이터 기반 학생 파악 및 AI 자동 생성 보충 자료로 행정·지도 하중 대폭 완화</p>
                </div>
              </div>
            </div>

            <!-- B2C -->
            <div class="bg-slate-800 border-t-8 border-t-blue-500 rounded-3xl p-8 hover:-translate-y-2 transition-transform duration-300">
              <div class="w-16 h-16 bg-blue-500/20 rounded-2xl flex items-center justify-center text-3xl mb-6">🎒</div>
              <h4 class="text-3xl font-bold text-white mb-6">B2C<br><span class="text-blue-400 text-xl">(오직 학생을 위해)</span></h4>
              
              <div class="space-y-6">
                <div>
                  <h5 class="text-xl font-bold text-slate-200 mb-2 flex items-center"><span class="text-blue-500 mr-2">💣</span> 심리적 진입 장벽 분쇄</h5>
                  <p class="text-slate-400">수료하지 못해도 그동안 배운 지식이 '내 스킬블록' 포트폴리오로 남아 안도감 부여</p>
                </div>
                <div>
                  <h5 class="text-xl font-bold text-slate-200 mb-2 flex items-center"><span class="text-blue-500 mr-2">⚡</span> 압도적인 학습 효율</h5>
                  <p class="text-slate-400">내가 모르는 내용, 취약 구역만 정밀 타격하여 복습하는 초개인화 학습 경험</p>
                </div>
              </div>
            </div>
          </div>
        </section>

        <!-- 8. 한계점 및 향후 계획 -->
        <section v-else-if="currentSlide === 7" class="w-full">
           <div class="flex items-center gap-4 mb-4">
            <span class="text-purple-500 text-2xl">🚀</span>
            <h2 class="text-2xl font-bold text-purple-400 tracking-wider">LIMITATION & FUTURE</h2>
          </div>
          <h3 class="text-5xl font-bold text-white mb-10">한계점 및 확장 로드맵</h3>

          <div class="bg-slate-800/80 p-6 rounded-2xl border-l-4 border-slate-500 mb-10">
            <h4 class="text-xl font-bold text-slate-300 mb-2">현재의 한계 (Limitations)</h4>
            <p class="text-slate-400">HTTP 기반 양방향 레이턴시 제약 / 외부 LLM API 비용 문제 / 단일 강좌용 DB 설계</p>
          </div>

          <h4 class="text-2xl font-bold text-white mb-6">Phase 2 확장 로드맵</h4>
          <div class="grid grid-cols-3 gap-6">
            <div class="bg-slate-800 p-6 rounded-2xl border border-slate-700/50 hover:border-purple-500/50 transition-colors">
              <div class="text-3xl mb-4">⚡</div>
              <h5 class="text-xl font-bold text-white mb-3">초실시간성 (WebSocket)</h5>
              <p class="text-sm text-slate-400">Socket.io를 연결하여 이해도 펄스 등 강사-학생 간 제로 딜레이 통신 및 실시간 출석 기능 도입</p>
            </div>
            
            <div class="bg-slate-800 p-6 rounded-2xl border border-slate-700/50 hover:border-blue-500/50 transition-colors">
              <div class="text-3xl mb-4">🌐</div>
              <h5 class="text-xl font-bold text-white mb-3">B2B SaaS 아키텍처</h5>
              <p class="text-sm text-slate-400">멀티 테넌시, 다중 워크스페이스를 통해 실제 기업들의 사내 교육 관리가 가능한 통합 플랫폼으로 격상</p>
            </div>

            <div class="bg-slate-800 p-6 rounded-2xl border border-slate-700/50 hover:border-teal-500/50 transition-colors">
              <div class="text-3xl mb-4">🔒</div>
              <h5 class="text-xl font-bold text-white mb-3">프라이버시 & 로컬 sLLM</h5>
              <p class="text-sm text-slate-400">AI 기본법 완벽 대응 및 기업 내부 정보 유출 방지를 위한 자체망 소형 언어 모델 탑재 기반 마련</p>
            </div>
          </div>
        </section>

        <!-- 9. Q&A -->
        <section v-else-if="currentSlide === 8" class="w-full h-full flex flex-col items-center justify-center text-center relative">
          <!-- Background glow -->
          <div class="absolute w-[600px] h-[600px] bg-blue-500/20 rounded-full blur-[100px] z-0"></div>
          
          <div class="z-10 bg-slate-900/50 backdrop-blur-xl p-16 rounded-3xl border border-slate-700/50 shadow-2xl min-w-[700px]">
            <h1 class="text-8xl font-black mb-8 text-transparent bg-clip-text bg-gradient-to-br from-blue-400 to-teal-400 tracking-widest">Q & A</h1>
            <p class="text-3xl text-slate-300 font-medium mb-12">경청해 주셔서 감사합니다.</p>
            <div class="inline-block bg-slate-800 px-8 py-4 rounded-xl border border-slate-700">
              <p class="text-slate-400 text-lg mb-2">프레젠테이션 : <strong>Re:Boot 4조</strong></p>
              <p class="text-slate-400 text-lg">발표자 : <strong>김혜진</strong></p>
            </div>
          </div>
        </section>

      </transition>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'

const currentSlide = ref(0)
const totalSlides = 9
const container = ref(null)

const progress = computed(() => {
  return ((currentSlide.value) / (totalSlides - 1)) * 100
})

const nextSlide = () => {
  if (currentSlide.value < totalSlides - 1) {
    currentSlide.value++
  }
}

const prevSlide = () => {
  if (currentSlide.value > 0) {
    currentSlide.value--
  }
}

onMounted(() => {
  if (container.value) {
    container.value.focus()
  }
})
</script>

<style scoped>
.slide-fade-enter-active {
  transition: all 0.5s ease-out;
}
.slide-fade-leave-active {
  transition: all 0.4s cubic-bezier(1, 0.5, 0.8, 1);
}
.slide-fade-enter-from {
  transform: translateY(30px);
  opacity: 0;
}
.slide-fade-leave-to {
  transform: translateY(-30px);
  opacity: 0;
}

/* Background blob animations */
@keyframes blob {
  0% {
    transform: translate(0px, 0px) scale(1);
  }
  33% {
    transform: translate(30px, -50px) scale(1.1);
  }
  66% {
    transform: translate(-20px, 20px) scale(0.9);
  }
  100% {
    transform: translate(0px, 0px) scale(1);
  }
}
.animate-blob {
  animation: blob 7s infinite;
}
.animation-delay-2000 {
  animation-delay: 2s;
}
.animation-delay-4000 {
  animation-delay: 4s;
}
</style>

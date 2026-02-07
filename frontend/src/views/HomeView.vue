<template>
  <div class="home-view">
    <section class="hero-section">
      <div class="container">
        <h1 class="text-headline">
          Re:Boot Your Career.<br />
          <span class="gradient-text">AI Powered.</span>
        </h1>
        <p class="text-subhead">
          실시간 경로 재설계로 완주를 보장하는<br />
          가장 진보된 커리어 빌드업 플랫폼.
        </p>
        <div class="cta-group">
          <button class="btn btn-primary btn-lg">무료로 시작하기</button>
          <button class="btn btn-secondary btn-lg">더 알아보기</button>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped lang="scss">
.home-view {
  padding-top: 100px;
  text-align: center;
}

.hero-section {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 60vh;
}

.text-headline {
  font-size: 64px;
  margin-bottom: 24px;

  .gradient-text {
    background: linear-gradient(135deg, #0071e3 0%, #42a1ff 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
  }
}

.text-subhead {
  max-width: 600px;
  margin: 0 auto 40px;
  line-height: 1.6;
}

.cta-group {
  display: flex;
  gap: 16px;
  justify-content: center;

  .btn-lg {
    padding: 12px 28px;
    font-size: 14px;
  }
}
</style>

from flask import Flask, render_template

app = Flask(__name__)

# 메인 프레젠테이션 페이지 라우팅
@app.route('/')
def presentation():
    return render_template('index.html')

if __name__ == '__main__':
    # 디버그 모드로 5001번 포트에서 실행합니다. (Mac AirPlay 포트 충돌 방지)
    app.run(debug=True, host='0.0.0.0', port=5001)

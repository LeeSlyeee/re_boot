import socket
import numpy as np
import tensorflow as tf
from tensorflow.contrib.framework.python.ops import audio_ops as contrib_audio
import collections
import time
import os
import json
import urllib.request
import urllib.error

# --- 1. 파라미터 및 통신 설정 ---
HOST = '0.0.0.0'  # 모든 인터페이스에서 접속 허용
PORT = 9999       # 포트 번호
DJANGO_WEBHOOK_URL = os.environ.get('DJANGO_WEBHOOK_URL', 'http://127.0.0.1:8000/api/learning/live/kws-webhook/') # 배포 시 PC의 IP로 변경 필요

SAMPLE_RATE = 16000
CHUNK_DURATION_MS = 250
CHUNK_SIZE = int(SAMPLE_RATE * CHUNK_DURATION_MS / 1000)  # 4000 samples
WINDOW_SIZE_MS = 40.0
WINDOW_STRIDE_MS = 20.0
DCT_COEFFICIENT_COUNT = 10
CLIP_DURATION_SAMPLES = SAMPLE_RATE

LABELS = ['_silence_', '_unknown_', 'quiz', 'understand']
PB_MODEL_PATH = "work/ds_cnn_korean_frozen.pb"

if not os.path.exists(PB_MODEL_PATH):
    PB_MODEL_PATH = "ds_cnn_korean_frozen.pb"

if not os.path.exists(PB_MODEL_PATH):
    print(f"❌ 오류: '{PB_MODEL_PATH}' 파일을 찾을 수 없습니다!")
    exit(1)

# --- 2. TF 세션 및 그래프 구축 ---
tf.reset_default_graph()
sess = tf.compat.v1.InteractiveSession()
wav_placeholder = tf.placeholder(tf.float32, [CLIP_DURATION_SAMPLES, 1])

# MFCC 추출 그래프
spectrogram = contrib_audio.audio_spectrogram(
    wav_placeholder,
    window_size=int(SAMPLE_RATE * WINDOW_SIZE_MS / 1000),
    stride=int(SAMPLE_RATE * WINDOW_STRIDE_MS / 1000),
    magnitude_squared=True)
mfcc_op = contrib_audio.mfcc(
    spectrogram,
    SAMPLE_RATE,
    dct_coefficient_count=DCT_COEFFICIENT_COUNT)
mfcc_flatten = tf.reshape(mfcc_op, [1, -1])

# --- 3. Frozen Graph 로드 ---
graph_def = tf.compat.v1.GraphDef()
with tf.io.gfile.GFile(PB_MODEL_PATH, 'rb') as f:
    graph_def.ParseFromString(f.read())
tf.import_graph_def(graph_def, name='frozen_model')

model_graph = tf.compat.v1.get_default_graph()
fingerprint_input = model_graph.get_tensor_by_name("frozen_model/Reshape:0")
probabilities_op = model_graph.get_tensor_by_name("frozen_model/labels_softmax:0")

# --- 4. 안정성 로직 세팅 ---
window_history = collections.deque(maxlen=2) # 2 -> 1 (즉각적인 반응 우선)
suppression_counter = 0 
SUPPRESSION_PULL_DOWN = 6                     
audio_buffer = np.zeros(CLIP_DURATION_SAMPLES, dtype=np.float32)

def recvall(sock, n):
    """지정된 바이트 수(n)만큼 소켓에서 완전히 읽어오는 헬퍼 함수"""
    data = bytearray()
    while len(data) < n:
        packet = sock.recv(n - len(data))
        if not packet:
            return None
        data.extend(packet)
    return data

# --- 5. 소켓 서버 구동 ---
server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server_socket.bind((HOST, PORT))
server_socket.listen(1)

print(f"\n==== 📡 소켓 서버 시작 (포트: {PORT}) ====")
print(f"모델 파일: {PB_MODEL_PATH}")
print("PC(클라이언트)의 연결을 대기 중입니다...\n")

while True:
    client_socket, addr = server_socket.accept()
    print(f"\n✅ 클라이언트 연결됨: {addr}")
    
    # 연결될 때마다 버퍼 초기화
    audio_buffer = np.zeros(CLIP_DURATION_SAMPLES, dtype=np.float32)
    window_history.clear()
    suppression_counter = 0
    
    try:
        while True:
            # 16bit(2 bytes) * 4000 samples = 8000 bytes
            raw_data = recvall(client_socket, CHUNK_SIZE * 2)
            
            if not raw_data:
                print(f"클라이언트({addr}) 연결 종료")
                break
            
            # Int16 -> Float32 [-1.0, 1.0] 정규화
            audio_chunk_int16 = np.frombuffer(raw_data, dtype=np.int16)
            audio_chunk = audio_chunk_int16.astype(np.float32) / 32768.0
            
            # [최적화] DC Offset 제거 (편향된 신호 보정)
            audio_chunk = audio_chunk - np.mean(audio_chunk)
            
            # 슬라이딩 윈도우 업데이트
            audio_buffer = np.roll(audio_buffer, -CHUNK_SIZE)
            audio_buffer[-CHUNK_SIZE:] = audio_chunk
            
            # 전체 1초 버퍼에 대한 볼륨 (정규화 전)
            raw_volume = np.max(np.abs(audio_buffer))
            
            # [핵심] 피크 정규화 (Peak Normalization)
            # 모델이 가장 잘 인식하도록 입력 신호의 피크를 1.0(또는 0.9)으로 고정
            inf_buffer = audio_buffer.copy()
            norm_factor = 1.0
            if raw_volume > 0.005:
                norm_factor = 0.8 / raw_volume
                inf_buffer = inf_buffer * norm_factor
            
            # MFCC 변환 및 추론
            mfcc_feat = sess.run(mfcc_flatten, feed_dict={wav_placeholder: inf_buffer.reshape(-1, 1)})
            probs = sess.run(probabilities_op, feed_dict={fingerprint_input: mfcc_feat})[0]
            
            window_history.append(probs)
            
            if len(window_history) >= 1:
                smoothed_output = np.mean(window_history, axis=0)
                sorted_indices = np.argsort(smoothed_output)[::-1]
                top_index = sorted_indices[0]
                top_score = smoothed_output[top_index]
                prediction = LABELS[top_index]
                
                debug_info = ", ".join([f"{LABELS[idx]}: {smoothed_output[idx]*100:.1f}%" for idx in sorted_indices[:3]])
                timestamp = time.strftime("%H:%M:%S") + f".{int(time.time()*1000)%1000:03d}"

                if suppression_counter > 0:
                    suppression_counter -= 1
                    print(f"[{timestamp}] (보류중 {suppression_counter}) [{debug_info}] 볼륨:{raw_volume:.3f} (x{norm_factor:.1f})")
                    continue
                
                if raw_volume < 0.005: # 최소 소리 기준 상향
                    print(f"[{timestamp}] (_silence_) 볼륨:{raw_volume:.3f}")
                    continue
                
                # 트리거 로직
                target_triggered = None
                quiz_score = smoothed_output[LABELS.index('quiz')]
                understand_score = smoothed_output[LABELS.index('understand')]
                
                if quiz_score >= 0.1:
                    target_triggered = 'quiz'
                    target_score = quiz_score
                elif understand_score >= 0.1:
                    target_triggered = 'understand'
                    target_score = understand_score
                
                if target_triggered:
                    print(f"[{timestamp}] 🔥 {target_triggered.upper()} 포착! (점수: {target_score*100:.1f}%) [{debug_info}] 볼륨:{raw_volume:.3f} (x{norm_factor:.1f})")
                    client_socket.sendall(f"TRIGGER_{target_triggered.upper()}\n".encode('utf-8'))
                    
                    # [Phase 3 통신 혁신] Django 서버로 "나 퀴즈 찾았다"고 단 1건의 텍스트 신호만 발송 (urllib 사용)
                    try:
                        payload = {"keyword": target_triggered.upper(), "confidence": float(target_score)}
                        data = json.dumps(payload).encode('utf-8')
                        req = urllib.request.Request(DJANGO_WEBHOOK_URL, data=data, headers={'Content-Type': 'application/json'}, method='POST')
                        
                        try:
                            with urllib.request.urlopen(req, timeout=2) as response:
                                res_body = response.read().decode('utf-8')
                                res_json = json.loads(res_body)
                                print(f"[{timestamp}] 🌐 웹훅 발사 성공: {res_json.get('message', 'OK')}")
                        except urllib.error.HTTPError as e:
                            print(f"[{timestamp}] ⚠️ 웹훅 발사 실패 (서버 응답: {e.code})")
                        except urllib.error.URLError as e:
                            print(f"[{timestamp}] ❌ 웹훅 전송 실패 (서버 접속 불가): {e.reason}")
                    except Exception as e:
                        print(f"[{timestamp}] ❌ 웹훅 전송 준비 중 오류: {e}")

                    suppression_counter = 4 # 약 1초 대기
                else:
                    print(f"[{timestamp}] ({debug_info}) 볼륨:{raw_volume:.3f} (x{norm_factor:.1f})")

    except ConnectionResetError:
        print(f"⚠️ 클라이언트({addr}) 비정상 종료")
    finally:
        client_socket.close()

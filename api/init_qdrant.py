import pandas as pd
from app.qdrant.collection import create_collection
from app.qdrant.init_data import insert_initial_data


if __name__ == "__main__":
    print("=" * 50) 
    print("Qdrant Collection 초기화 시작")
    print("=" * 50)

    # 0. 임베딩 모델 로딩 (추가!)
    print("\n[0/3] 임베딩 모델 로딩 중...")
    from app.utils.embedding import embedding_service
    embedding_service.load_model()
    print("✓ 모델 로딩 완료!")

    # 1. 컬렉션 생성
    print("\n[1/3] Collection 생성 중...")
    create_collection()
    print("✓ Collection 생성 완료!")

    # 2. 초기 데이터 삽입
    print("\n[2/3] 초기 데이터 삽입 중...")

    # CSV 파일 확인
    import os
    csv_path = "train_data.csv"
    if not os.path.exists(csv_path):
        print(f"⚠️  CSV 파일 없음: {csv_path}")
        print("테스트 샘플 데이터만 생성합니다.")
        # 최소 샘플 데이터로 대체
        df = pd.DataFrame([
            {"field": "thesis", "content": "본 논문에서는 자연어 처리를 제안한다.", "intensity": "strong"},
            {"field": "email", "content": "안녕하세요, 보고서 잘 받았습니다.", "intensity": "weak"},
            {"field": "report", "content": "2024년 실적은 15% 증가했습니다.", "intensity": "moderate"},
        ])
    else:
        df = pd.read_csv(csv_path)

    print(f"총 {len(df)}개의 데이터를 삽입합니다.")

    batch_size = 500
    for start in range(0, len(df), batch_size):
        insert_initial_data(df.iloc[start:start+batch_size], start_id=start)
        print(f"진행: {min(start + batch_size, len(df))}/{len(df)}")

    # 3. 검증
    print("\n[3/3] 검증 중...")
    from app.qdrant.client import get_qdrant_client
    client = get_qdrant_client()
    info = client.get_collection("context_block_v1")
    print(f"✓ Collection: context_block_v1")
    print(f"✓ Points count: {info.points_count}")

    print("\n" + "=" * 50)
    print("초기화 완료!")
    print("=" * 50)

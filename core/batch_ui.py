"""Simple upload-free batch workflow, with optional advanced controls."""
import hashlib
import zipfile
from pathlib import PurePosixPath
import pandas as pd
import streamlit as st
from core.batch import analyze_batch, batch_csv, zip_inputs
from core.detector import Config
from core.dataset import bundled_files
from core.comparison import comparison_images


@st.cache_data(show_spinner=False, max_entries=2)
def load_bundled(group):
    return bundled_files(group)


@st.cache_data(show_spinner=False, max_entries=8)
def comparison(data, config, expected_count, expected_sha):
    return comparison_images(data, config, expected_count, expected_sha)


def preview(files, group):
    images = [(n,d) for n,d in files if n.endswith('.png')]
    if not images:
        return
    page = st.selectbox('사진 페이지', range(1, (len(images)+11)//12+1), key=f'preview_{group}')
    shown = images[(page-1)*12:page*12]
    st.image([d for _,d in shown], caption=[PurePosixPath(n).name for n,_ in shown], width=150)


def show_comparison(rows, files, cfg, fingerprint):
    image_data = dict(files)
    choices = [i for i,r in enumerate(rows) if r.get('image_name') in image_data]
    if not choices:
        return
    st.subheader('② 사진으로 결과 확인')
    chosen = st.selectbox('확인할 사진', choices,
        format_func=lambda i: PurePosixPath(rows[i]['image_name']).name + (' · 주석 오류' if rows[i]['status']=='error' else ''),
        key=f'comparison_{fingerprint[:16]}')
    row = rows[chosen]
    data = image_data[row['image_name']]
    if row['status'] != 'ok':
        st.warning(f"이 사진은 정답 검증을 하지 못했습니다: {row['message']}")
        try:
            from core.detector import read_image
            st.image(read_image(data), caption='분석 전 · 원본', use_container_width=True)
        except (ValueError, OSError):
            st.error('사진을 열 수 없습니다.')
        return
    before, after = comparison(data, cfg, row['auto_count'], row['image_sha256'])
    a,b,c=st.columns(3)
    a.metric('자동으로 센 수', f"{row['auto_count']}개")
    b.metric('정답 개수', f"{row['ground_truth_count']}개")
    c.metric('개수 차이', f"{row['absolute_error']}개")
    left,right=st.columns(2)
    left.image(before, caption='분석 전 · 원본', use_container_width=True)
    right.image(after, caption='분석 후 · 검출 위치 표시', use_container_width=True)
    st.caption('초록색 원: 자동으로 센 세포 후보 · 주황색 원: 불확실한 영역(계수 제외). 초록색 표시가 모두 실제 세포라는 뜻은 아닙니다.')
    st.download_button('이 분석 사진 저장', after, f"{PurePosixPath(row['image_name']).stem}_detected.png", 'image/png')


def render_batch():
    st.subheader('사진 속 세포, 한 번에 확인하세요')
    st.write('사진 464장이 준비되어 있습니다. 분석 시작을 누르면 원본과 검출 표시를 비교할 수 있습니다.')
    run_slot=st.container()
    files=[]
    cfg=Config()
    try:
        with st.expander('다른 사진 선택 · 분석 설정 (선택 사항)'):
            source=st.radio('데이터 준비 방법', ['준비된 CIDACC 전체 데이터','이미지와 TXT 함께 업로드','CIDACC ZIP 업로드'])
            if source=='준비된 CIDACC 전체 데이터':
                group=st.radio('사진 종류',['개별 세포 · 464장','뭉친 세포 · 164장'])
                if group=='뭉친 세포 · 164장':
                    cluster_view=True
                    files=load_bundled('clusters')
                else:
                    cluster_view=False
                    files=load_bundled('distinct')
                    selection=st.radio('분석 범위',['전체 464장','일부 사진 선택'])
                    if selection=='일부 사진 선택':
                        names=[n for n,_ in files if n.endswith('.png')]
                        selected=st.multiselect('분석할 사진',names,default=names[:10])
                        stems={PurePosixPath(n).stem for n in selected}
                        files=[(n,d) for n,d in files if PurePosixPath(n).stem in stems]
            elif source=='CIDACC ZIP 업로드':
                cluster_view=False
                up=st.file_uploader('CIDACC ZIP',type=['zip'])
                if up:
                    files=zip_inputs(up.getvalue())
                    names=[n for n,_ in files if '/images/' in n and n.lower().endswith('.png')]
                    selected=st.multiselect('분석할 사진 (최대 464장)',sorted(names),default=sorted(names),max_selections=464)
                    stems={PurePosixPath(n).stem.casefold() for n in selected}
                    files=[(n,d) for n,d in files if n in selected or (n.lower().endswith('.txt') and PurePosixPath(n).stem.casefold() in stems)]
            else:
                cluster_view=False
                st.write('distinct 이미지와 같은 이름의 정답 TXT를 함께 선택하세요.')
                uploads=st.file_uploader('PNG 사진과 bbs TXT',type=['png','txt'],accept_multiple_files=True)
                files=[(u.name,u.getvalue()) for u in uploads]
            if not cluster_view:
                mode=st.selectbox('검출 방식',['auto','gray','green'])
                sensitivity=st.slider('민감도',0,100,50,key='batch_sensitivity')
                a,b=st.columns(2)
                minimum=a.number_input('최소 면적(px²)',min_value=1,value=18,key='batch_min')
                maximum=b.number_input('최대 면적(px²)',min_value=1,value=2200,key='batch_max')
                cfg=Config(mode=mode,sensitivity=sensitivity,min_area=minimum,max_area=maximum)
        if cluster_view:
            st.warning('뭉친 세포 사진은 개별 세포 정답 개수를 확인하기 어려워 사진만 볼 수 있습니다.')
            preview(files,'clusters')
            return
        count=sum(PurePosixPath(n).suffix.lower() in ('.png','.jpg','.jpeg') for n,_ in files)
        fingerprint=hashlib.sha256(repr(([(n,hashlib.sha256(d).hexdigest()) for n,d in files],cfg)).encode()).hexdigest()
        if run_slot.button(f'① 분석 시작 · {count}장',disabled=not files,type='primary',use_container_width=True):
            with st.spinner('사진을 분석하고 있습니다…'):
                bar=st.progress(0)
                st.session_state['batch_result']=(fingerprint,analyze_batch(files,cfg,progress=lambda done,total:bar.progress(done/total,text=f'{done} / {total}장 처리')))
                bar.empty()
        saved=st.session_state.get('batch_result')
        if saved and saved[0]==fingerprint:
            rows=saved[1]
            good=[r for r in rows if r['status']=='ok']
            st.success(f"분석 완료 · 정상 {len(good)}장 / 확인이 필요한 파일 {len(rows)-len(good)}건")
            show_comparison(rows,files,cfg,fingerprint)
            st.subheader('③ 전체 결과 저장')
            st.download_button('전체 결과 CSV 다운로드',batch_csv(rows),'cidacc_batch_validation.csv','text/csv')
            with st.expander('전체 결과표 · 오류 내용 보기'):
                if good:
                    st.metric('평균 개수 차이(MAE)',round(sum(r['absolute_error'] for r in good)/len(good),3))
                table=pd.DataFrame(rows)
                st.dataframe(table.reindex(columns=['image_name','auto_count','ground_truth_count','absolute_error','percentage_error','status','message']).rename(columns={
                    'image_name':'사진','auto_count':'자동 계수','ground_truth_count':'정답 개수','absolute_error':'절대오차','percentage_error':'오차율(%)','status':'상태','message':'안내'}),hide_index=True)
                st.caption('정답이 없거나 잘못된 사진은 오차 계산에서 제외합니다. 정답이 0개면 백분율오차를 계산하지 않습니다.')
        elif saved:
            st.info('사진 또는 설정이 바뀌었습니다. 분석 시작을 다시 눌러 주세요.')
        else:
            st.caption('처음에는 설정을 바꾸지 않고 분석 시작을 눌러 보세요.')
        with st.expander('이 앱과 데이터 안내'):
            st.write('OpenCV 이미지 처리 도구이며 학습형 AI가 아닙니다. 격자선을 세포로 잘못 셀 수 있어 분석 후 사진을 확인하세요.')
            st.caption('출처: Pistolas et al. (2024), [CIDACC](https://doi.org/10.5281/zenodo.13219972), [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). 사진·TXT는 원본 그대로 포함했습니다.')
            st.caption('클래스 0은 개별 세포, 1은 뭉침(계수 제외)입니다. 원본 335.txt, 515.txt는 비어 있어 오류로 안내합니다.')
    except (ValueError,OSError,zipfile.BadZipFile,RuntimeError) as exc:
        st.error(f'분석할 수 없습니다: {exc}')

# Extracted source: export__2_.docx

> 원본 Word 파일에서 추출한 전략 리서치 텍스트입니다. 원본 docx는 Git ignore 대상이며, 이 Markdown은 전략 등록/분석을 위한 참조본입니다.

코스피 200 종목의 당일 양봉 마감을 예측하기 위한 데이트레이딩{{1}} 알고리즘의 핵심 산출 공식과 정교화 로직을 제안합니다. 이 시스템은 변동성 돌파{{2}}, 정보 기반 거래 확률(VPIN), 그리고 패턴 매칭 기술을 결합하여 진입 시점의 신뢰도를 극대화합니다.알고리즘 핵심 산출 공식래리 윌리엄스 변동성 돌파 진입가변동성 돌파 전략의 핵심은 전일의 가격 변동폭에 특정 계수를 곱하여 당일의 추세 전환점을 산출하는 것입니다. 진입 가격인 \(Price_{entry}\)는 다
음
과 같이 정의됩니다.\[Price_{entry} = Open_{today} + k \cdot (High_{yesterday} - Low_{yesterday})\]여기서 \(k\)는 변동성{{3}} 계수로, 코스피 200 시장 특성에 따라 통상 0.25에서 0.50 사이의 값이 권장됩니다.거래량 동기화 정보거래 확률 (VPIN)VPIN{{4}}은 고빈도 매매 환경에서 정보에 정통한 투자자의 거래 비중을 측정하여 유동성 독성과 변동성을 예측합니다. 산출 공식은 다
음
과 같습니다.\[VPIN = \frac{\sum_{\tau=1}^{n} |V_{\tau}^{S} - V_{\tau}^{B}|}{n \cdot V}\]\(V_{\tau}^{B}\)와 \(V_{\tau}^{S}\)는 각 거래량 버킷{{5}} 내에서의 매수 및 매도 거래량을 의미하며, \(n\)은 분석에 사용된 전체 버킷의 수, \(V\)는 각 버킷의 고정 거래량 크기입니다.벌크 거래량 분류 (BVC)개별 체결 데이터가 아닌 일정 기간의 데이터를 활용하여 매수/매도 압력을 추정하는 BVC{{6}} 알고리즘은 다
음
과 같이 매수 비중을 계산합니다.\[V^{B} = V \cdot \Phi\left(\frac{\Delta P}{\sigma \cdot \sqrt{\Delta t}}\right)\]여기서 \(\Phi\)는 표준정규분포의 누적분포함수이며, \(\Delta P\)는 가격 변화량, \(\sigma\)는 변동성을 의미합니다.매수 스코어링 정교화 로직시계열 패턴 매칭 및 동적 시간 워핑 (DTW)장 초반 90분간의 가격 흐름을 과거 90일간의 성공적인 양봉{{7}} 패턴과 비교하여 유사도를 산출합니다. DTW(Dynamic Time Warping) 알고리즘을 통해 시간축의 미세한 왜곡을 보정하고 현재의 가격 움직임
이 과거의 어떤 수익 패턴과 가장 유사한지 식별하여 점수화합니다.투자자별 수급 및 시장 미시구조 반영외국인 및 기관 투자자의 순매수{{8}} 압력과 옵션 내재 변동성 역학을 결합하여 수급 점수를 정교화합니다. 특히 VPIN 수치가 임
계치인 0.9(CDF 기준)를 초과할 때 발생하는 가격 반전 신호를 감지하여 역발상 진입이나 추세 강화 신호로 활용합니다.장 마감 전 처분 효과 제어데이 트레이더들이 손실 종목을 마감 직전에 강제로 청산하는 처분 효과{{9}}를 알고리즘에 반영하여 오후장 수급 변동을 예측합니다. 성공적인 투자자들의 패턴을 학습하여 장 후반 강제 손실 실현으로 인한 하락 압력을 피하고, 양봉 마감 가능성이 높은 종목에 가중치를 부여합니다.알고리즘 진입 로직 요
약 테이블
  <w:tblPr>
    <w:tblStyle w:val="a3"/>
    <w:tblW w:w="0" w:type="auto"/>
    <w:tblInd w:w="0" w:type="dxa"/>
    <w:tblLook w:val="04A0" w:firstRow="1" w:lastRow="0" w:firstColumn="1" w:lastColumn="0" w:noHBand="0" w:noVBand="1"/>
    <w:tblBorders>
      <w:top w:val="single" w:sz="3" w:space="1" w:color="000000"/>
      <w:bottom w:val="single" w:sz="3" w:space="1" w:color="000000"/>
      <w:left w:val="single" w:sz="3" w:space="1" w:color="000000"/>
      <w:right w:val="single" w:sz="3" w:space="1" w:color="000000"/>
      <w:insideH w:val="single" w:sz="3" w:space="1" w:color="000000"/>
      <w:insideV w:val="single" w:sz="3" w:space="1" w:color="000000"/>
    </w:tblBorders>
  </w:tblPr>
  <w:tblLayout w:type="auto"/>
  <w:tblGrid>
    <w:gridCol w:w="2666"/>
    <w:gridCol w:w="2666"/>
    <w:gridCol w:w="2666"/>
  </w:tblGrid>
  <w:tr w:rsidR="00995B51" w:rsidTr="007F1D13">
    <w:tc>
      <w:tcPr>
        <w:gridSpan w:val="1"/>
        <w:vAlign w:val="top"/>
        <w:tcW w:w="2666" w:type="dxa"/>
        <w:shd w:val="clear" w:color="auto" w:fill="f5f5f5" w:themeFill="" w:themeFillTint=""/>
      </w:tcPr>
      <w:p w:rsidR="00995B51" w:rsidRPr="00722E63" w:rsidRDefault="00995B51">
        <w:pPr>
          <w:keepNext w:val="0"/>
          <w:keepLines w:val="0"/>
          <w:pageBreakBefore w:val="0"/>
          <w:widowControl/>
          <w:kinsoku/>
          <w:wordWrap/>
          <w:overflowPunct/>
          <w:topLinePunct w:val="0"/>
          <w:autoSpaceDE/>
          <w:autoSpaceDN/>
          <w:bidi w:val="0"/>
          <w:adjustRightInd/>
          <w:snapToGrid/>
          <w:spacing w:before="100" w:after="100" w:line="240" w:lineRule="atLeast"/>
          <w:jc w:val="left"/>
          <w:textAlignment w:val="auto"/>
        </w:pPr>
        <w:r w:rsidRPr="00722E63">
          <w:rPr>
            <w:rFonts w:ascii="Arial" w:hAnsi="Arial"/>
            <w:color w:val="000000"/>
            <w:sz w:val="21"/>
            <w:szCs w:val="21"/>
          </w:rPr>
          <w:t>로직 구분
      <w:tcPr>
        <w:gridSpan w:val="1"/>
        <w:vAlign w:val="top"/>
        <w:tcW w:w="2666" w:type="dxa"/>
        <w:shd w:val="clear" w:color="auto" w:fill="f5f5f5" w:themeFill="" w:themeFillTint=""/>
      </w:tcPr>
      <w:p w:rsidR="00995B51" w:rsidRPr="00722E63" w:rsidRDefault="00995B51">
        <w:pPr>
          <w:keepNext w:val="0"/>
          <w:keepLines w:val="0"/>
          <w:pageBreakBefore w:val="0"/>
          <w:widowControl/>
          <w:kinsoku/>
          <w:wordWrap/>
          <w:overflowPunct/>
          <w:topLinePunct w:val="0"/>
          <w:autoSpaceDE/>
          <w:autoSpaceDN/>
          <w:bidi w:val="0"/>
          <w:adjustRightInd/>
          <w:snapToGrid/>
          <w:spacing w:before="100" w:after="100" w:line="240" w:lineRule="atLeast"/>
          <w:jc w:val="left"/>
          <w:textAlignment w:val="auto"/>
        </w:pPr>
        <w:r w:rsidRPr="00722E63">
          <w:rPr>
            <w:rFonts w:ascii="Arial" w:hAnsi="Arial"/>
            <w:color w:val="000000"/>
            <w:sz w:val="21"/>
            <w:szCs w:val="21"/>
          </w:rPr>
          <w:t>적용 공식 및 수치
      <w:tcPr>
        <w:gridSpan w:val="1"/>
        <w:vAlign w:val="top"/>
        <w:tcW w:w="2666" w:type="dxa"/>
        <w:shd w:val="clear" w:color="auto" w:fill="f5f5f5" w:themeFill="" w:themeFillTint=""/>
      </w:tcPr>
      <w:p w:rsidR="00995B51" w:rsidRPr="00722E63" w:rsidRDefault="00995B51">
        <w:pPr>
          <w:keepNext w:val="0"/>
          <w:keepLines w:val="0"/>
          <w:pageBreakBefore w:val="0"/>
          <w:widowControl/>
          <w:kinsoku/>
          <w:wordWrap/>
          <w:overflowPunct/>
          <w:topLinePunct w:val="0"/>
          <w:autoSpaceDE/>
          <w:autoSpaceDN/>
          <w:bidi w:val="0"/>
          <w:adjustRightInd/>
          <w:snapToGrid/>
          <w:spacing w:before="100" w:after="100" w:line="240" w:lineRule="atLeast"/>
          <w:jc w:val="left"/>
          <w:textAlignment w:val="auto"/>
        </w:pPr>
        <w:r w:rsidRPr="00722E63">
          <w:rPr>
            <w:rFonts w:ascii="Arial" w:hAnsi="Arial"/>
            <w:color w:val="000000"/>
            <w:sz w:val="21"/>
            <w:szCs w:val="21"/>
          </w:rPr>
          <w:t>정교화 목표
    <w:tc>
      <w:tcPr>
        <w:gridSpan w:val="1"/>
        <w:vAlign w:val="top"/>
        <w:tcW w:w="2666" w:type="dxa"/>
      </w:tcPr>
      <w:p w:rsidR="00995B51" w:rsidRPr="00722E63" w:rsidRDefault="00995B51">
        <w:pPr>
          <w:keepNext w:val="0"/>
          <w:keepLines w:val="0"/>
          <w:pageBreakBefore w:val="0"/>
          <w:widowControl/>
          <w:kinsoku/>
          <w:wordWrap/>
          <w:overflowPunct/>
          <w:topLinePunct w:val="0"/>
          <w:autoSpaceDE/>
          <w:autoSpaceDN/>
          <w:bidi w:val="0"/>
          <w:adjustRightInd/>
          <w:snapToGrid/>
          <w:spacing w:before="100" w:after="100" w:line="240" w:lineRule="atLeast"/>
          <w:jc w:val="left"/>
          <w:textAlignment w:val="auto"/>
        </w:pPr>
        <w:r w:rsidRPr="00722E63">
          <w:rPr>
            <w:rFonts w:ascii="Arial" w:hAnsi="Arial"/>
            <w:color w:val="000000"/>
            <w:sz w:val="21"/>
            <w:szCs w:val="21"/>
          </w:rPr>
          <w:t>가격 돌파
      <w:tcPr>
        <w:gridSpan w:val="1"/>
        <w:vAlign w:val="top"/>
        <w:tcW w:w="2666" w:type="dxa"/>
      </w:tcPr>
      <w:p w:rsidR="00995B51" w:rsidRPr="00722E63" w:rsidRDefault="00995B51">
        <w:pPr>
          <w:keepNext w:val="0"/>
          <w:keepLines w:val="0"/>
          <w:pageBreakBefore w:val="0"/>
          <w:widowControl/>
          <w:kinsoku/>
          <w:wordWrap/>
          <w:overflowPunct/>
          <w:topLinePunct w:val="0"/>
          <w:autoSpaceDE/>
          <w:autoSpaceDN/>
          <w:bidi w:val="0"/>
          <w:adjustRightInd/>
          <w:snapToGrid/>
          <w:spacing w:before="100" w:after="100" w:line="240" w:lineRule="atLeast"/>
          <w:jc w:val="left"/>
          <w:textAlignment w:val="auto"/>
        </w:pPr>
        <w:r w:rsidRPr="00722E63">
          <w:rPr>
            <w:rFonts w:ascii="Arial" w:hAnsi="Arial"/>
            <w:color w:val="000000"/>
            <w:sz w:val="21"/>
            <w:szCs w:val="21"/>
          </w:rPr>
          <w:t>\(k = 0.5\) 기준 변동성 돌파 공식
      <w:tcPr>
        <w:gridSpan w:val="1"/>
        <w:vAlign w:val="top"/>
        <w:tcW w:w="2666" w:type="dxa"/>
      </w:tcPr>
      <w:p w:rsidR="00995B51" w:rsidRPr="00722E63" w:rsidRDefault="00995B51">
        <w:pPr>
          <w:keepNext w:val="0"/>
          <w:keepLines w:val="0"/>
          <w:pageBreakBefore w:val="0"/>
          <w:widowControl/>
          <w:kinsoku/>
          <w:wordWrap/>
          <w:overflowPunct/>
          <w:topLinePunct w:val="0"/>
          <w:autoSpaceDE/>
          <w:autoSpaceDN/>
          <w:bidi w:val="0"/>
          <w:adjustRightInd/>
          <w:snapToGrid/>
          <w:spacing w:before="100" w:after="100" w:line="240" w:lineRule="atLeast"/>
          <w:jc w:val="left"/>
          <w:textAlignment w:val="auto"/>
        </w:pPr>
        <w:r w:rsidRPr="00722E63">
          <w:rPr>
            <w:rFonts w:ascii="Arial" w:hAnsi="Arial"/>
            <w:color w:val="000000"/>
            <w:sz w:val="21"/>
            <w:szCs w:val="21"/>
          </w:rPr>
          <w:t>장중 추세 발생 시 즉각적인 진입 타점 확보
    <w:tc>
      <w:tcPr>
        <w:gridSpan w:val="1"/>
        <w:vAlign w:val="top"/>
        <w:tcW w:w="2666" w:type="dxa"/>
      </w:tcPr>
      <w:p w:rsidR="00995B51" w:rsidRPr="00722E63" w:rsidRDefault="00995B51">
        <w:pPr>
          <w:keepNext w:val="0"/>
          <w:keepLines w:val="0"/>
          <w:pageBreakBefore w:val="0"/>
          <w:widowControl/>
          <w:kinsoku/>
          <w:wordWrap/>
          <w:overflowPunct/>
          <w:topLinePunct w:val="0"/>
          <w:autoSpaceDE/>
          <w:autoSpaceDN/>
          <w:bidi w:val="0"/>
          <w:adjustRightInd/>
          <w:snapToGrid/>
          <w:spacing w:before="100" w:after="100" w:line="240" w:lineRule="atLeast"/>
          <w:jc w:val="left"/>
          <w:textAlignment w:val="auto"/>
        </w:pPr>
        <w:r w:rsidRPr="00722E63">
          <w:rPr>
            <w:rFonts w:ascii="Arial" w:hAnsi="Arial"/>
            <w:color w:val="000000"/>
            <w:sz w:val="21"/>
            <w:szCs w:val="21"/>
          </w:rPr>
          <w:t>수급 독성
      <w:tcPr>
        <w:gridSpan w:val="1"/>
        <w:vAlign w:val="top"/>
        <w:tcW w:w="2666" w:type="dxa"/>
      </w:tcPr>
      <w:p w:rsidR="00995B51" w:rsidRPr="00722E63" w:rsidRDefault="00995B51">
        <w:pPr>
          <w:keepNext w:val="0"/>
          <w:keepLines w:val="0"/>
          <w:pageBreakBefore w:val="0"/>
          <w:widowControl/>
          <w:kinsoku/>
          <w:wordWrap/>
          <w:overflowPunct/>
          <w:topLinePunct w:val="0"/>
          <w:autoSpaceDE/>
          <w:autoSpaceDN/>
          <w:bidi w:val="0"/>
          <w:adjustRightInd/>
          <w:snapToGrid/>
          <w:spacing w:before="100" w:after="100" w:line="240" w:lineRule="atLeast"/>
          <w:jc w:val="left"/>
          <w:textAlignment w:val="auto"/>
        </w:pPr>
        <w:r w:rsidRPr="00722E63">
          <w:rPr>
            <w:rFonts w:ascii="Arial" w:hAnsi="Arial"/>
            <w:color w:val="000000"/>
            <w:sz w:val="21"/>
            <w:szCs w:val="21"/>
          </w:rPr>
          <w:t>VPIN 임
계치 0.9 초과 여부
      <w:tcPr>
        <w:gridSpan w:val="1"/>
        <w:vAlign w:val="top"/>
        <w:tcW w:w="2666" w:type="dxa"/>
      </w:tcPr>
      <w:p w:rsidR="00995B51" w:rsidRPr="00722E63" w:rsidRDefault="00995B51">
        <w:pPr>
          <w:keepNext w:val="0"/>
          <w:keepLines w:val="0"/>
          <w:pageBreakBefore w:val="0"/>
          <w:widowControl/>
          <w:kinsoku/>
          <w:wordWrap/>
          <w:overflowPunct/>
          <w:topLinePunct w:val="0"/>
          <w:autoSpaceDE/>
          <w:autoSpaceDN/>
          <w:bidi w:val="0"/>
          <w:adjustRightInd/>
          <w:snapToGrid/>
          <w:spacing w:before="100" w:after="100" w:line="240" w:lineRule="atLeast"/>
          <w:jc w:val="left"/>
          <w:textAlignment w:val="auto"/>
        </w:pPr>
        <w:r w:rsidRPr="00722E63">
          <w:rPr>
            <w:rFonts w:ascii="Arial" w:hAnsi="Arial"/>
            <w:color w:val="000000"/>
            <w:sz w:val="21"/>
            <w:szCs w:val="21"/>
          </w:rPr>
          <w:t>정보 기반 거래 급증에 따른 변동성 확대 대비
    <w:tc>
      <w:tcPr>
        <w:gridSpan w:val="1"/>
        <w:vAlign w:val="top"/>
        <w:tcW w:w="2666" w:type="dxa"/>
      </w:tcPr>
      <w:p w:rsidR="00995B51" w:rsidRPr="00722E63" w:rsidRDefault="00995B51">
        <w:pPr>
          <w:keepNext w:val="0"/>
          <w:keepLines w:val="0"/>
          <w:pageBreakBefore w:val="0"/>
          <w:widowControl/>
          <w:kinsoku/>
          <w:wordWrap/>
          <w:overflowPunct/>
          <w:topLinePunct w:val="0"/>
          <w:autoSpaceDE/>
          <w:autoSpaceDN/>
          <w:bidi w:val="0"/>
          <w:adjustRightInd/>
          <w:snapToGrid/>
          <w:spacing w:before="100" w:after="100" w:line="240" w:lineRule="atLeast"/>
          <w:jc w:val="left"/>
          <w:textAlignment w:val="auto"/>
        </w:pPr>
        <w:r w:rsidRPr="00722E63">
          <w:rPr>
            <w:rFonts w:ascii="Arial" w:hAnsi="Arial"/>
            <w:color w:val="000000"/>
            <w:sz w:val="21"/>
            <w:szCs w:val="21"/>
          </w:rPr>
          <w:t>패턴 유사도
      <w:tcPr>
        <w:gridSpan w:val="1"/>
        <w:vAlign w:val="top"/>
        <w:tcW w:w="2666" w:type="dxa"/>
      </w:tcPr>
      <w:p w:rsidR="00995B51" w:rsidRPr="00722E63" w:rsidRDefault="00995B51">
        <w:pPr>
          <w:keepNext w:val="0"/>
          <w:keepLines w:val="0"/>
          <w:pageBreakBefore w:val="0"/>
          <w:widowControl/>
          <w:kinsoku/>
          <w:wordWrap/>
          <w:overflowPunct/>
          <w:topLinePunct w:val="0"/>
          <w:autoSpaceDE/>
          <w:autoSpaceDN/>
          <w:bidi w:val="0"/>
          <w:adjustRightInd/>
          <w:snapToGrid/>
          <w:spacing w:before="100" w:after="100" w:line="240" w:lineRule="atLeast"/>
          <w:jc w:val="left"/>
          <w:textAlignment w:val="auto"/>
        </w:pPr>
        <w:r w:rsidRPr="00722E63">
          <w:rPr>
            <w:rFonts w:ascii="Arial" w:hAnsi="Arial"/>
            <w:color w:val="000000"/>
            <w:sz w:val="21"/>
            <w:szCs w:val="21"/>
          </w:rPr>
          <w:t>DTW 기반 시계열 패턴 매칭
      <w:tcPr>
        <w:gridSpan w:val="1"/>
        <w:vAlign w:val="top"/>
        <w:tcW w:w="2666" w:type="dxa"/>
      </w:tcPr>
      <w:p w:rsidR="00995B51" w:rsidRPr="00722E63" w:rsidRDefault="00995B51">
        <w:pPr>
          <w:keepNext w:val="0"/>
          <w:keepLines w:val="0"/>
          <w:pageBreakBefore w:val="0"/>
          <w:widowControl/>
          <w:kinsoku/>
          <w:wordWrap/>
          <w:overflowPunct/>
          <w:topLinePunct w:val="0"/>
          <w:autoSpaceDE/>
          <w:autoSpaceDN/>
          <w:bidi w:val="0"/>
          <w:adjustRightInd/>
          <w:snapToGrid/>
          <w:spacing w:before="100" w:after="100" w:line="240" w:lineRule="atLeast"/>
          <w:jc w:val="left"/>
          <w:textAlignment w:val="auto"/>
        </w:pPr>
        <w:r w:rsidRPr="00722E63">
          <w:rPr>
            <w:rFonts w:ascii="Arial" w:hAnsi="Arial"/>
            <w:color w:val="000000"/>
            <w:sz w:val="21"/>
            <w:szCs w:val="21"/>
          </w:rPr>
          <w:t>과거 수익 사례와의 형태적 유사성 검증
    <w:tc>
      <w:tcPr>
        <w:gridSpan w:val="1"/>
        <w:vAlign w:val="top"/>
        <w:tcW w:w="2666" w:type="dxa"/>
      </w:tcPr>
      <w:p w:rsidR="00995B51" w:rsidRPr="00722E63" w:rsidRDefault="00995B51">
        <w:pPr>
          <w:keepNext w:val="0"/>
          <w:keepLines w:val="0"/>
          <w:pageBreakBefore w:val="0"/>
          <w:widowControl/>
          <w:kinsoku/>
          <w:wordWrap/>
          <w:overflowPunct/>
          <w:topLinePunct w:val="0"/>
          <w:autoSpaceDE/>
          <w:autoSpaceDN/>
          <w:bidi w:val="0"/>
          <w:adjustRightInd/>
          <w:snapToGrid/>
          <w:spacing w:before="100" w:after="100" w:line="240" w:lineRule="atLeast"/>
          <w:jc w:val="left"/>
          <w:textAlignment w:val="auto"/>
        </w:pPr>
        <w:r w:rsidRPr="00722E63">
          <w:rPr>
            <w:rFonts w:ascii="Arial" w:hAnsi="Arial"/>
            <w:color w:val="000000"/>
            <w:sz w:val="21"/>
            <w:szCs w:val="21"/>
          </w:rPr>
          <w:t>수급 분류
      <w:tcPr>
        <w:gridSpan w:val="1"/>
        <w:vAlign w:val="top"/>
        <w:tcW w:w="2666" w:type="dxa"/>
      </w:tcPr>
      <w:p w:rsidR="00995B51" w:rsidRPr="00722E63" w:rsidRDefault="00995B51">
        <w:pPr>
          <w:keepNext w:val="0"/>
          <w:keepLines w:val="0"/>
          <w:pageBreakBefore w:val="0"/>
          <w:widowControl/>
          <w:kinsoku/>
          <w:wordWrap/>
          <w:overflowPunct/>
          <w:topLinePunct w:val="0"/>
          <w:autoSpaceDE/>
          <w:autoSpaceDN/>
          <w:bidi w:val="0"/>
          <w:adjustRightInd/>
          <w:snapToGrid/>
          <w:spacing w:before="100" w:after="100" w:line="240" w:lineRule="atLeast"/>
          <w:jc w:val="left"/>
          <w:textAlignment w:val="auto"/>
        </w:pPr>
        <w:r w:rsidRPr="00722E63">
          <w:rPr>
            <w:rFonts w:ascii="Arial" w:hAnsi="Arial"/>
            <w:color w:val="000000"/>
            <w:sz w:val="21"/>
            <w:szCs w:val="21"/>
          </w:rPr>
          <w:t>BVC 기반 실시간 매수 비중 산출
      <w:tcPr>
        <w:gridSpan w:val="1"/>
        <w:vAlign w:val="top"/>
        <w:tcW w:w="2666" w:type="dxa"/>
      </w:tcPr>
      <w:p w:rsidR="00995B51" w:rsidRPr="00722E63" w:rsidRDefault="00995B51">
        <w:pPr>
          <w:keepNext w:val="0"/>
          <w:keepLines w:val="0"/>
          <w:pageBreakBefore w:val="0"/>
          <w:widowControl/>
          <w:kinsoku/>
          <w:wordWrap/>
          <w:overflowPunct/>
          <w:topLinePunct w:val="0"/>
          <w:autoSpaceDE/>
          <w:autoSpaceDN/>
          <w:bidi w:val="0"/>
          <w:adjustRightInd/>
          <w:snapToGrid/>
          <w:spacing w:before="100" w:after="100" w:line="240" w:lineRule="atLeast"/>
          <w:jc w:val="left"/>
          <w:textAlignment w:val="auto"/>
        </w:pPr>
        <w:r w:rsidRPr="00722E63">
          <w:rPr>
            <w:rFonts w:ascii="Arial" w:hAnsi="Arial"/>
            <w:color w:val="000000"/>
            <w:sz w:val="21"/>
            <w:szCs w:val="21"/>
          </w:rPr>
          <w:t>대량 거래 발생 시 실제 공격적 매수 주체 식별
    <w:tc>
      <w:tcPr>
        <w:gridSpan w:val="1"/>
        <w:vAlign w:val="top"/>
        <w:tcW w:w="2666" w:type="dxa"/>
      </w:tcPr>
      <w:p w:rsidR="00995B51" w:rsidRPr="00722E63" w:rsidRDefault="00995B51">
        <w:pPr>
          <w:keepNext w:val="0"/>
          <w:keepLines w:val="0"/>
          <w:pageBreakBefore w:val="0"/>
          <w:widowControl/>
          <w:kinsoku/>
          <w:wordWrap/>
          <w:overflowPunct/>
          <w:topLinePunct w:val="0"/>
          <w:autoSpaceDE/>
          <w:autoSpaceDN/>
          <w:bidi w:val="0"/>
          <w:adjustRightInd/>
          <w:snapToGrid/>
          <w:spacing w:before="100" w:after="100" w:line="240" w:lineRule="atLeast"/>
          <w:jc w:val="left"/>
          <w:textAlignment w:val="auto"/>
        </w:pPr>
        <w:r w:rsidRPr="00722E63">
          <w:rPr>
            <w:rFonts w:ascii="Arial" w:hAnsi="Arial"/>
            <w:color w:val="000000"/>
            <w:sz w:val="21"/>
            <w:szCs w:val="21"/>
          </w:rPr>
          <w:t>모멘텀 지속
      <w:tcPr>
        <w:gridSpan w:val="1"/>
        <w:vAlign w:val="top"/>
        <w:tcW w:w="2666" w:type="dxa"/>
      </w:tcPr>
      <w:p w:rsidR="00995B51" w:rsidRPr="00722E63" w:rsidRDefault="00995B51">
        <w:pPr>
          <w:keepNext w:val="0"/>
          <w:keepLines w:val="0"/>
          <w:pageBreakBefore w:val="0"/>
          <w:widowControl/>
          <w:kinsoku/>
          <w:wordWrap/>
          <w:overflowPunct/>
          <w:topLinePunct w:val="0"/>
          <w:autoSpaceDE/>
          <w:autoSpaceDN/>
          <w:bidi w:val="0"/>
          <w:adjustRightInd/>
          <w:snapToGrid/>
          <w:spacing w:before="100" w:after="100" w:line="240" w:lineRule="atLeast"/>
          <w:jc w:val="left"/>
          <w:textAlignment w:val="auto"/>
        </w:pPr>
        <w:r w:rsidRPr="00722E63">
          <w:rPr>
            <w:rFonts w:ascii="Arial" w:hAnsi="Arial"/>
            <w:color w:val="000000"/>
            <w:sz w:val="21"/>
            <w:szCs w:val="21"/>
          </w:rPr>
          <w:t>장 초반 30분 오프닝 레인지 돌파
      <w:tcPr>
        <w:gridSpan w:val="1"/>
        <w:vAlign w:val="top"/>
        <w:tcW w:w="2666" w:type="dxa"/>
      </w:tcPr>
      <w:p w:rsidR="00995B51" w:rsidRPr="00722E63" w:rsidRDefault="00995B51">
        <w:pPr>
          <w:keepNext w:val="0"/>
          <w:keepLines w:val="0"/>
          <w:pageBreakBefore w:val="0"/>
          <w:widowControl/>
          <w:kinsoku/>
          <w:wordWrap/>
          <w:overflowPunct/>
          <w:topLinePunct w:val="0"/>
          <w:autoSpaceDE/>
          <w:autoSpaceDN/>
          <w:bidi w:val="0"/>
          <w:adjustRightInd/>
          <w:snapToGrid/>
          <w:spacing w:before="100" w:after="100" w:line="240" w:lineRule="atLeast"/>
          <w:jc w:val="left"/>
          <w:textAlignment w:val="auto"/>
        </w:pPr>
        <w:r w:rsidRPr="00722E63">
          <w:rPr>
            <w:rFonts w:ascii="Arial" w:hAnsi="Arial"/>
            <w:color w:val="000000"/>
            <w:sz w:val="21"/>
            <w:szCs w:val="21"/>
          </w:rPr>
          <w:t>일중 모멘텀(MIM)의 유효성 및 수익성 극대화IMPORTANT DISCLAIMER: 이 보고서는 일반적인 정보 제공을 목적으로 하며, 특정 종목에 대한 투자 권유나 금융{{10}} 자문을 대신할 수 없습니다. 실제 투자 결정 전 반드시 전문가와 상의하시기 바랍니다.출처[1]  @article{Choi_Song_2021, title={Is it possible to forecast KOSPI direction using deep learning methods?}, url={http://www.csam.or.kr/journal/view.html?doi=10.29220/CSAM.2021.28.4.329}, journal={Communications for Statistical Applications and Methods}, author={Choi, Songa and Song, Jongwoo}, year={2021}, month=july }[2]  @article{Eom_2020, title={Intraday disposition effect of day traders and its relationship with investment performance: evidence from the KOSPI 200 futures market}, url={https://www.tandfonline.com/doi/full/10.1080/13504851.2019.1676374}, journal={Applied Economics Letters}, author={Eom, Yunsung}, year={2020}, month=aug }[3]  @article{Jung_Park_2019, title={A Comparative Test for the Information Contents between Futures Market and Option Market : Using VPIN}, url={http://www.dbpia.co.kr/Journal/ArticleDetail/NODE08007715}, journal={Journal of Industrial Economics and Business}, author={Jung, Daesung and Park, JongHae}, year={2019}, month=apr }[4]  @article{Kang_Kwon_Kim_2020, title={Flow toxicity of high‐frequency trading and its impact on price volatility: Evidence from the KOSPI 200 futures market}, url={https://onlinelibrary.wiley.com/doi/10.1002/fut.22062}, journal={Journal of Futures Markets}, author={Kang, Jangkoo and Kwon, Kyung Yoon and Kim, Wooyeon}, year={2020}, month=feb }[5]  @article{Kim_Lee_Ko_Jeong_Byun_Oh_2018, title={Pattern Matching Trading System Based on the Dynamic Time Warping Algorithm}, url={https://www.mdpi.com/2071-1050/10/12/4641}, journal={Sustainability}, author={Kim, Sang Hyuk and Lee, Hee Soo and Ko, Han Jun and Jeong, Seunghwan and Byun, Hyun Woo and Oh, Kyong Joo}, year={2018}, month=oct }[6]  @article{Kwon_Kang_Chung_2018, title={Performance of Option Based Strategy Benchmark Index}, url={https://www.emerald.com/insight/content/doi/10.1108/JDQS-02-2018-B0002/full/html}, journal={Journal of Derivatives and Quantitative Studies 선물연구}, author={Kwon, Soon Shin and Kang, Byung Jin and Chung, Jay M.}, year={2018}, month=may }[7]  @article{Lai_Zhen-yu_Eom_Tsai_2022, title={Market Intraday Momentum with New Measures for Trading Cost: Evidence from KOSPI Index}, url={https://www.mdpi.com/1911-8074/15/11/523}, journal={Journal of risk and financial management}, author={Lai, Chien-Yuan and Zhen-yu, Lin and Eom, Cheoljun and Tsai, Ping Chen}, year={2022}, month=nov }[8]  @article{Lee_Chen_Ryu_2025, title={Effectiveness of domain stabilization: A broader perspective}, url={https://linkinghub.elsevier.com/retrieve/pii/S1059056025009621}, journal={International Review of Economics & Finance}, author={Lee, Geul and Chen, Jing and Ryu, Doojin}, year={2025}, month=dec }[9]  @article{Quinn_6610, title={FIVE-FACTOR MARKET-NEUTRAL STRATEGY ACROSS KOREAN AND US EQUITY MARKETS: STRUCTURAL ALPHA WITHOUT REGIME FILTERS}, url={https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6610458}, journal={Available at SSRN 6610458}, author={Quinn, P}, year={6610}, month=jan }[10]  @article{Ryu_Webb_Yang_Yu_2021, title={Investors’ net buying pressure and implied volatility dynamics}, url={https://linkinghub.elsevier.com/retrieve/pii/S2214845021000934}, journal={Borsa Istanbul Review}, author={Ryu, Doojin and Webb, Robert I. and Yang, Heejin and Yu, Jinyoung}, year={2021}, month=sept }[11]  @article{김서경_2020, title={KOSPI200 지수선물 괴리율:수요
기반이론 설명과 미래현물수익률에 대한 예측}, url={https://www.earticle.net/Article/A369806}, journal={상업교육연구}, author={김서경}, year={2020}, month=feb }[12]  @misc{Bulk Volume Classification Algorithm_2018, url={https://quant.stackexchange.com/questions/43103/bulk-volume-classification-algorithm}, year={2018}, month=dec }[13]  @misc{Measuring Toxic Flow for Trading & Risk Management_2021, url={https://jonathankinlay.com/2021/02/measuring-toxic-flow-for-trading-risk-management/}, year={2021}, month=feb }[14]  @misc{[PDF] Multi-Timeframe Algorithmic Trading Bots Using Thick Data …_2022, url={https://wiserpub.com/uploads/1/20221205/f3c8fa871419c7b6c14065fa26253a2a.pdf}, year={2022}, month=dec }[15]  @misc{Order Flow Toxicity Explained: A Complete Guide to VPIN - YouTube_2025, url={https://www.youtube.com/watch?v=gO2IZLhwejs}, year={2025}, month=dec }[16]  @misc{Volatility Breakout Strategy (TradingView) - 192 Backtests, url={https://tradesearcher.ai/strategies/1666-volatility-breakout-strategy} }[17]  @misc{About VPIN(Volume-Synchronized Probability of Informed …, url={https://medium.com/@jaaeehoonkim/about-vpin-volume-synchronized-probability-of-informed-trading-eddd76bcc48e} }[18]  @misc{VPIN (Volume-synchronized Probability of Informed Trading), url={https://questdb.com/docs/cookbook/sql/finance/vpin/} }[19]  @misc{VPIN - Volume Synchronized Probability of Informed Trading - GitHub, url={https://github.com/SGTYang/VPIN} }[20]  @misc{yt-feng/VPIN: Order flow toxicity; Volume-Synchronized …, url={https://github.com/yt-feng/VPIN} }[21]  @misc{An Improved Version of the Volume-Synchronized Probability …, url={https://cfr.ivo-welch.info/forthcoming/papers/ke-lin.pdf} }[22]  @misc{An Improved Version of the Volume-Synchronized …, url={https://ideas.repec.org/a/now/jnlcfr/104.00000047.html} }[23]  @misc{Estimation of Volume-Synchronized PIN model - Search R-project.org, url={https://search.r-project.org/CRAN/refmans/PINstimation/html/vpin.html} }[24]  @misc{[PDF] VPIN 1 The Volume Synchronized Probability of INformed Trading …, url={https://www.quantresearch.org/VPIN.pdf} }[25]  @misc{[PDF] Bulk Volume Trade Classification and Informed Trading*, url={http://faculty.bus.olemiss.edu/rvanness/Speakers/Presentations 2019-2020/AlCarrion_BVC_info_Jan2020.pdf} }[26]  @misc{A New Way to Compute the Probability of Informed Trading, url={https://www.scirp.org/journal/paperinformation?paperid=95972} }[27]  @misc{Parameter Analysis of the VPIN (Volume synchronized Probability of …, url={https://escholarship.org/uc/item/2sr9m6gk} }[28]  @misc{Parameter Analysis of the VPIN (Volume synchronized …, url={https://sdm.lbl.gov/~kewu/ps/LBNL-6605E.html} }[29]  @misc{Measuring the Toxicity of Order Flow using High Frequency Data …, url={https://discovery.researcher.life/article/measuring-the-toxicity-of-order-flow-using-high-frequency-data-the-case-of-kospi200-index-futures/854ef36b507a34669ce6bbb7e1861d47} }[30]  @misc{Exchange Traded Barrier Options and Volume- …, url={https://acfr.aut.ac.nz/__data/assets/pdf_file/0005/29930/Adrian-Lei-CBBCVPIN_v4AUT.pdf} }[31]  @misc{[PDF] Bulk volume classification and information detection - thomas d. shohfi, url={https://tom.shohfi.com/don/pubs/01-Don-BVC.pdf} }[32]  @misc{[PDF] 1 Flow Toxicity and Liquidity in a High Frequency World … - NYU Stern, url={https://www.stern.nyu.edu/sites/default/files/assets/documents/con_035928.pdf} }[33]  @misc{[PDF] Trade Classification Algorithms: A Horse Race between the Bulk …, url={https://dee.uib.eu/digitalAssets/234/234006_Pascual.pdf} }[34]  @misc{Bulk volume classification and information detection - IDEAS/RePEc, url={https://ideas.repec.org/a/eee/jbfina/v103y2019icp113-129.html} }[35]  @misc{[PDF] Bulk Volume Classification Under the Microscope - ACFR - AUT, url={https://acfr.aut.ac.nz/__data/assets/pdf_file/0016/222037/ROBERTO-Massot-Samarpan-and-Pascual-2018-BVC-and-NOF-Preliminary-and-incomplete.pdf} }[36]  @misc{Results of the KOSPI200 prediction based on [2] method, url={https://www.researchgate.net/figure/Results-of-the-KOSPI200-prediction-based-on-2-method_tbl2_321066887} }[37]  @misc{An intelligent hybrid trading system for discovering trading rules for …, url={https://www.researchgate.net/publication/313537413_An_intelligent_hybrid_trading_system_for_discovering_trading_rules_for_the_futures_market_using_rough_sets_and_genetic_algorithms} }

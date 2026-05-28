# Extracted source: export.docx

> 원본 Word 파일에서 추출한 전략 리서치 텍스트입니다. 원본 docx는 Git ignore 대상이며, 이 Markdown은 전략 등록/분석을 위한 참조본입니다.

코스피 200 종목의 데이트레이딩을 위해 변동성 돌파{{1}}, 수급 분석{{2}}, 장초반 모멘텀{{3}} 지표를 기반으로 한 구체적인 진입 수치와 기술적 근거를 제안합니다.변동성 기반 진입 수치래리 윌리엄스 변동성 돌파 전략래리 윌리엄스{{4}}의 변동성 돌파 전략은 전일의 고가와 저가 차이(변동폭)에 특정 계수(K)를 곱한 값을 당일 시가에 더하여 진입가를 산출합니다. 일반적으로 K-값은 0.5가 널리 쓰이나, 시장 상황에 따라 최적화가 필요
하며 일부 연구에서는 0.25를 기준으로 하기도 합니다. 코스피 200 선물 시장의 실현 변동성 분석에 따르면, 장중 가격 변동폭을 활용한 추세 추종 방식이 유효한 진입 근거가 됩니다.변동성 중단(VI) 임
계치 활용한국거래소의 변동성 완화장치{{5}}(VI) 규정에 따르면, 코스피 200 구성 종목의 동적 VI 발동 임
계치는 연속 매매 시간 동안 3%로 설정되어 있습니다. 종가 단일가 매매 시간에는 이 임
계치가 2%로 조정됩니다. 데이트레이더는 이러한 제도적 변동성 임
계치를 가격 돌파의 강도를 확인하는 기준으로 활용할 수 있습니다.수급 및 모멘텀 진입 수치VPIN 및 정보 기반 거래정보에 정통한 투자자의 거래 비중을 나타내는 VPIN{{6}} 지표는 시장의 유동성 독성을 파악하는 데 사용됩니다. 코스피 200 시장에서 BV-VPIN 수치가 누적 분포 함수(CDF) 기준 0.9를 초과할 경우, 이는 극심한 가격 변동이나 반전의 신호로 해석될 수 있습니다. 고빈도 매매(HFT) 투자자들은 하루 1,000건 이상의 지정가 주문을 제출하며 가격 발견에 기여하므로 이들의 수급 흐름을 모니터링하는 것이 중요
합니다.장초반 모멘텀 및 오프닝 레인지장 시작 후 초기 10분 동안의 추세가 장 마감까지 유지되는 가격 모멘텀{{7}} 효과를 활용한 전략이 유효할 수 있습니다. 일부 오프닝 레인지 돌파 전략에서는 30분 동안의 가격 범위를 기준으로 하며, 이 범위를 상향 돌파하거나 하향 돌파하는 시점을 주요 진입 타점으로 잡습니다. 이때 거래량이 직전 X개 봉 평균보다 10% 이상 증가하는 조건 등을 추가하여 진입 신호의 신뢰도를 높일 수 있습니다.데이트레이딩 최적 진입 스코어링 테이블아래 테이블은 코스피 200 데이트레이딩 알고리즘 설계를 위한 핵심 진입 수치를 정리한 것입니다.
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
          <w:t>분석 지표
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
          <w:t>권장 진입/참조 수치
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
          <w:t>수치적 근거 및 비고
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
          <w:t>변동성 돌파{{1}} (K-값)
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
          <w:t>0.25 ~ 0.50
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
          <w:t>전일 변동폭(고가-저가) 대비 돌파 계수
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
          <w:t>동적 VI 임
계치
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
          <w:t>3% (연속매매 중)
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
          <w:t>코스피 200 종목 대상 정적/동적 변동성 완화 기준
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
          <w:t>VPIN{{6}} 임
계치
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
          <w:t>0.9 (CDF 값)
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
          <w:t>정보 기반 거래 급증에 따른 변동성 확대 신호
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
          <w:t>거래량 급증 기준
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
          <w:t>평균 대비 10% 이상
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
          <w:t>오프닝 레인지 돌파 시 신뢰도 확인 지표
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
          <w:t>모멘텀 관찰 시간
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
          <w:t>장 초반 10분 ~ 30분
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
          <w:t>장중 추세 지속성 확인을 위한 초기 설정 시간
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
          <w:t>RSI{{8}} 과매도/과매수
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
          <w:t>45.7 (현재 중립 수준)
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
          <w:t>14일 기준 지수 강도 지표로 현재는 중립 구간임
면책 조항: 이 보고서는 일반적인 정보 제공을 목적으로 하며, 특정 종목에 대한 투자 권유나 금융 자문을 대신할 수 없습니다. 실제 투자 결정 전 반드시 전문가와 상의하시기 바랍니다.출처[1]  @misc{Larry Williams volatility breakout | BEST Strategy Ever! - YouTube_2022, url={https://www.youtube.com/watch?v=Blx6D_i1yAk}, year={2022}, month=july }[2]  @misc{I Backtested Larry Williams’ Trading Strategy Across 15 Markets_2025, url={https://roguequant.substack.com/p/i-backtested-larry-williams-trading}, year={2025}, month=apr }[3]  @misc{why don’t more people do 15 minute opening range breakout …_2025, url={https://www.reddit.com/r/Daytrading/comments/1lgk0cp/why_dont_more_people_do_15_minute_opening_range/}, year={2025}, month=june }[4]  @misc{Opening Range Breakout Strategy up 400% This Year (Strict Rules …_2025, url={https://tradethatswing.com/opening-range-breakout-strategy-up-400-this-year/?srsltid=AfmBOoq1vumlcaeSMLWHsc6puAp4J9R3iiZtBncL5f_fKR-F7SNd1GFd}, year={2025}, month=oct }[5]  @misc{KOSPI Volatility Surges to Highest Since Pandemic_2026, url={https://www.chosun.com/english/market-money-en/2026/02/13/BHGRCM47WRDWZERGQEEXMLKMKY/}, year={2026}, month=feb }[6]  @misc{Trading KOSPI200 weekly index options 101 - Reddit_2026, url={https://www.reddit.com/r/options/comments/1rfy5v7/trading_kospi200_weekly_index_options_101/}, year={2026}, month=feb }[7]  @misc{LW Volatility Breakout [Confirmed] — Indicator by ArisCodes_2026, url={https://www.tradingview.com/script/hw1O8Y4i-LW-Volatility-Breakout-Confirmed/}, year={2026}, month=mar }[8]  @misc{KOSPI Triggers Critical Buy-Side Trading Curb After Dramatic Surge_2026, url={https://cryptorank.io/news/feed/29d1b-kospi-buy-side-trading-curb}, year={2026}, month=apr }[9]  @misc{Opening Range Breakout: 0DTE Options Trading Strategy Explained_2026, url={https://optionalpha.com/blog/opening-range-breakout-0dte-options-trading-strategy-explained}, year={2026}, month=apr }[10]  @misc{Volatility Breakouts and the Oops Reversal Setup | Larry Williams_2026, url={https://www.youtube.com/watch?v=NQxO__tXW5o}, year={2026}, month=apr }[11]  @misc{Dynamic and Static Volatility Interruptions: Evidence from the … - MDPI, url={https://www.mdpi.com/1911-8074/15/3/105} }[12]  @misc{Trading strategy: Larry Williams Volatility Break-out - WH SelfInvest, url={https://www.whselfinvest.com/en-fr/trading-platform/free-trading-strategies/tradingsystem/56-volatility-break-out-larry-williams-free} }[13]  @misc{The Larry Williams Volatility Break-out strategy, url={https://www.best-trading-platforms.com/trading-platform-futures-forex-cfd-stocks-nanotrader/larry-williams-volatility-break-out-strategy} }[14]  @misc{Larry Williams Volatility Channel Trading Strategy (Backtest and …, url={https://www.quantifiedstrategies.com/larry-williams-volatility-strategy/} }[15]  @misc{[PDF] Flow Toxicity of High Frequency Trading and Its Impact on Price …, url={https://www.efmaefm.org/0EFMAMEETINGS/EFMA ANNUAL MEETINGS/2019-Azores/papers/EFMA2019_0376_fullpaper.pdf} }[16]  @misc{[PDF] KOSPI200 지수선물시장에서, url={https://smallake.kr/wp-content/uploads/2024/11/KIRI_20240905_1.pdf} }[17]  @misc{BV‐VPIN around extreme price volatilities. The left top panel (a), the…, url={https://www.researchgate.net/figure/BV-VPIN-around-extreme-price-volatilities-The-left-top-panel-a-the-left-bottom-panel_fig1_336419747} }[18]  @misc{Larry Williams Market Secrets (Part 5): Automating the Volatility …, url={https://www.mql5.com/en/articles/20745} }[19]  @misc{Volatility Breakout Strategy (TradingView) - 192 Backtests, url={https://tradesearcher.ai/strategies/1666-volatility-breakout-strategy} }[20]  @misc{Analysis of intraday price momentum effect based on patterns …, url={https://www.kdiss.org/journal/view.html?uid=2240&&vmd=Full} }[21]  @misc{Technical Analysis of KOSPI 200 Index (KRX:KOSPI200), url={https://www.tradingview.com/symbols/KRX-KOSPI200/technicals/} }[22]  @misc{[PDF] Evidence from the KOSPI 200 Options Market, url={https://www.kdajdqs.org/bbs/reference/887/download/1534} }[23]  @misc{Market Intraday Momentum with New Measures for Trading …, url={https://ideas.repec.org/a/gam/jjrfmx/v15y2022i11p523-d966717.html} }[24]  @misc{Understanding intraday momentum strategies | Request PDF, url={https://www.researchgate.net/publication/363384228_Understanding_intraday_momentum_strategies} }[25]  @misc{[논문]호가잔량정보를 이용한 데이트레이딩전략의 수익성 분석 - kisti, url={https://scienceon.kisti.re.kr/srch/selectPORSrchArticle.do?cn=JAKO201922441756714} }[26]  @misc{변동성 측정방법에 따른 KOSPI200 지수의 변동성 예측 비교, url={https://www.kci.go.kr/kciportal/ci/sereArticleSearch/ciSereArtiView.kci?sereArticleSearchBean.artiId=ART001433740} }[27]  @misc{Opening Range Breakout Trading Strategy Design and …, url={https://easylanguagemastery.com/building-strategies/opening-range-breakout-trading-strategy-design-implementation/} }[28]  @misc{KOSPI 200 Technical Analysis and Moving Averages - Investing.com, url={https://www.investing.com/indices/kospi-200-technical} }

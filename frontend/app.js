const form = document.querySelector("#research-form");
const runButton = document.querySelector("#run-button");
const runMessage = document.querySelector("#run-message");

const serviceStatus = document.querySelector("#service-status");
const statusDot = document.querySelector(".status-dot");

const errorPanel = document.querySelector("#error-panel");
const errorMessage = document.querySelector("#error-message");

const resultPanel = document.querySelector("#result-panel");
const resultStatus = document.querySelector("#result-status");

const decisionQuestionOutput = document.querySelector(
    "#decision-question-output"
);
const contextOutput = document.querySelector("#context-output");
const horizonOutput = document.querySelector("#horizon-output");
const subquestionsOutput = document.querySelector(
    "#subquestions-output"
);
const criteriaOutput = document.querySelector("#criteria-output");
const searchQueriesOutput = document.querySelector(
    "#search-queries-output"
);

const evidencePanel = document.querySelector("#evidence-panel");
const evidenceCount = document.querySelector("#evidence-count");
const evidenceOutput = document.querySelector("#evidence-output");

const decisionPanel = document.querySelector("#decision-panel");
const confidenceBadge = document.querySelector(
    "#confidence-badge"
);
const executiveSummaryOutput = document.querySelector(
    "#executive-summary-output"
);
const recommendationOutput = document.querySelector(
    "#recommendation-output"
);
const findingsOutput = document.querySelector(
    "#findings-output"
);
const alternativesOutput = document.querySelector(
    "#alternatives-output"
);
const risksOutput = document.querySelector("#risks-output");
const nextStepsOutput = document.querySelector(
    "#next-steps-output"
);

const translations = {
    horizon: {
        "90 days": "未来90天",
        "12 months": "未来12个月",
        "3 years": "未来3年",
    },
    sourceType: {
        government: "政府部门",
        academic: "学术研究",
        industry_report: "行业报告",
        company: "企业来源",
        news: "新闻媒体",
        other: "其他",
    },
    level: {
        high: "高",
        medium: "中",
        low: "低",
    },
    serviceStatus: {
        healthy: "正常",
    },
};


async function checkBackend() {
    try {
        const response = await fetch("/api/health");

        if (!response.ok) {
            throw new Error(
                "服务返回异常。"
            );
        }

        const data = await response.json();
        const localizedStatus =
            translations.serviceStatus[data.status]
            || data.status;

        serviceStatus.textContent =
            `服务状态：${localizedStatus}`;
        statusDot.classList.add("connected");
    } catch (error) {
        serviceStatus.textContent =
            "暂时无法连接服务";
        statusDot.classList.remove("connected");
    }
}


function renderList(element, items = []) {
    element.replaceChildren();

    items.forEach((item) => {
        const listItem = document.createElement("li");
        listItem.textContent = item;
        element.appendChild(listItem);
    });
}


function hideOutputPanels() {
    errorPanel.hidden = true;
    resultPanel.hidden = true;
    evidencePanel.hidden = true;
    decisionPanel.hidden = true;
}


function renderPlan(plan) {
    decisionQuestionOutput.textContent =
        plan.decision_question;

    contextOutput.textContent =
        plan.context || "未提供补充背景。";

    horizonOutput.textContent =
        translations.horizon[plan.horizon]
        || plan.horizon;

    renderList(
        subquestionsOutput,
        plan.subquestions
    );

    renderList(
        criteriaOutput,
        plan.success_criteria
    );

    renderList(
        searchQueriesOutput,
        plan.search_queries
    );

    resultStatus.textContent = "研究已完成";
    resultPanel.hidden = false;
}


function createTag(label, value, className) {
    const tag = document.createElement("span");

    tag.className = `evidence-tag ${className}`;
    tag.textContent = `${label}: ${value}`;

    return tag;
}


function getSafeUrl(value) {
    try {
        const url = new URL(value);

        if (
            url.protocol === "http:"
            || url.protocol === "https:"
        ) {
            return url.href;
        }
    } catch (error) {
        return null;
    }

    return null;
}


function prepareReviewedSources(
    evidenceBundles = [],
    assessments = []
) {
    const preparedSources = [];
    let sourceNumber = 1;

    evidenceBundles.forEach((bundle) => {
        const rankedRecords = [
            ...(bundle.records || []),
        ].sort(
            (first, second) =>
                second.relevance_score
                - first.relevance_score
        );

        const record = rankedRecords[0];

        if (!record) {
            return;
        }

        const sourceId = `S${sourceNumber}`;
        const assessment = assessments.find(
            (item) => item.source_id === sourceId
        );

        preparedSources.push({
            sourceId,
            query: bundle.query,
            record,
            assessment,
        });

        sourceNumber += 1;
    });

    return preparedSources;
}


function renderEvidence(
    evidenceBundles,
    assessments
) {
    evidenceOutput.replaceChildren();

    const sources = prepareReviewedSources(
        evidenceBundles,
        assessments
    );

    evidenceCount.textContent =
        `已评估 ${sources.length} 个来源`;

    const sourceLookup = new Map();

    if (sources.length === 0) {
        const emptyMessage = document.createElement("p");

        emptyMessage.className = "empty-message";
        emptyMessage.textContent =
            "未找到相关性足够高的证据。";

        evidenceOutput.appendChild(emptyMessage);
        evidencePanel.hidden = false;

        return sourceLookup;
    }

    sources.forEach((source) => {
        const {
            sourceId,
            query,
            record,
            assessment,
        } = source;

        sourceLookup.set(sourceId, source);

        const card = document.createElement("article");
        card.className = "evidence-card";

        const cardHeader = document.createElement("div");
        cardHeader.className = "evidence-card-header";

        const sourceLabel = document.createElement("span");
        sourceLabel.className = "source-id";
        sourceLabel.textContent = sourceId;

        const sourceLink = document.createElement("a");
        sourceLink.className = "source-link";
        sourceLink.textContent =
            record.title || "未命名来源";

        const safeUrl = getSafeUrl(record.url);

        if (safeUrl) {
            sourceLink.href = safeUrl;
            sourceLink.target = "_blank";
            sourceLink.rel = "noopener noreferrer";
        }

        cardHeader.append(
            sourceLabel,
            sourceLink
        );

        const tags = document.createElement("div");
        tags.className = "evidence-tags";

        if (assessment) {
            tags.append(
                createTag(
                    "类型",
                    translations.sourceType[
                        assessment.source_type
                    ] || assessment.source_type,
                    "neutral-tag"
                ),
                createTag(
                    "质量",
                    translations.level[
                        assessment.quality
                    ] || assessment.quality,
                    `quality-${assessment.quality}`
                ),
                createTag(
                    "相关性",
                    translations.level[
                        assessment.relevance
                    ] || assessment.relevance,
                    `relevance-${assessment.relevance}`
                )
            );
        }

        const queryText = document.createElement("p");
        queryText.className = "evidence-query";
        queryText.textContent = `检索词：${query}`;

        const claimHeading = document.createElement("h3");
        claimHeading.textContent = "支持的观点";

        const claimText = document.createElement("p");
        claimText.className = "evidence-claim";
        claimText.textContent = assessment
            ? assessment.key_claim
            : "证据评估未返回结果。";

        const limitationsHeading =
            document.createElement("h3");
        limitationsHeading.textContent = "局限性";

        const limitationsText =
            document.createElement("p");
        limitationsText.className =
            "evidence-limitations";
        limitationsText.textContent = assessment
            ? assessment.limitations
            : (
                "该来源尚未完成评估，需要人工核验。"
            );

        card.append(
            cardHeader,
            tags,
            queryText,
            claimHeading,
            claimText,
            limitationsHeading,
            limitationsText
        );

        evidenceOutput.appendChild(card);
    });

    evidencePanel.hidden = false;

    return sourceLookup;
}


function renderFindings(
    findings = [],
    sourceLookup
) {
    findingsOutput.replaceChildren();

    findings.forEach((finding) => {
        const listItem = document.createElement("li");
        listItem.className = "finding-item";

        const claim = document.createElement("p");
        claim.textContent = finding.claim;

        const citations = document.createElement("div");
        citations.className = "finding-citations";

        if (
            !finding.source_ids
            || finding.source_ids.length === 0
        ) {
            const noCitation =
                document.createElement("span");

            noCitation.textContent =
                "暂无可核验的来源引用";

            citations.appendChild(noCitation);
        } else {
            finding.source_ids.forEach((sourceId) => {
                const source = sourceLookup.get(sourceId);
                const citation =
                    document.createElement(
                        source ? "a" : "span"
                    );

                citation.className = "citation-chip";
                citation.textContent = sourceId;

                if (source) {
                    const safeUrl = getSafeUrl(
                        source.record.url
                    );

                    if (safeUrl) {
                        citation.href = safeUrl;
                        citation.target = "_blank";
                        citation.rel =
                            "noopener noreferrer";
                        citation.title =
                            source.record.title;
                    }
                }

                citations.appendChild(citation);
            });
        }

        listItem.append(
            claim,
            citations
        );

        findingsOutput.appendChild(listItem);
    });
}


function renderDecisionBrief(
    brief,
    sourceLookup
) {
    executiveSummaryOutput.textContent =
        brief.executive_summary;

    recommendationOutput.textContent =
        brief.recommendation;

    const confidence =
        brief.confidence || "low";

    confidenceBadge.textContent =
        `置信度：${translations.level[confidence] || confidence}`;

    confidenceBadge.classList.remove(
        "confidence-high",
        "confidence-medium",
        "confidence-low"
    );

    confidenceBadge.classList.add(
        `confidence-${confidence}`
    );

    renderFindings(
        brief.key_findings,
        sourceLookup
    );

    renderList(
        alternativesOutput,
        brief.alternatives
    );

    renderList(
        risksOutput,
        brief.risks
    );

    renderList(
        nextStepsOutput,
        brief.next_steps
    );

    decisionPanel.hidden = false;
}


form.addEventListener("submit", async (event) => {
    event.preventDefault();

    const requestData = {
        question: document
            .querySelector("#question")
            .value
            .trim(),
        context: document
            .querySelector("#context")
            .value
            .trim(),
        horizon: document
            .querySelector("#horizon")
            .value,
    };

    hideOutputPanels();

    runButton.disabled = true;
    runButton.textContent =
        "研究进行中……";

    const progressMessages = [
        "正在制定研究计划……",
        "正在检索相关证据……",
        "正在评估来源质量……",
        "正在生成决策简报……",
    ];

    let messageIndex = 0;

    runMessage.textContent =
        progressMessages[messageIndex];

    const progressTimer = window.setInterval(
        () => {
            messageIndex = (
                messageIndex + 1
            ) % progressMessages.length;

            runMessage.textContent =
                progressMessages[messageIndex];
        },
        4500
    );

    try {
        const response = await fetch(
            "/api/research",
            {
                method: "POST",
                headers: {
                    "Content-Type":
                        "application/json",
                },
                body: JSON.stringify(requestData),
            }
        );

        if (!response.ok) {
            throw new Error(
                "研究请求失败，状态码："
                + `${response.status}。`
            );
        }

        const data = await response.json();

        if (!data.plan) {
            throw new Error(
                "服务未返回研究计划。"
            );
        }

        if (!data.brief) {
            throw new Error(
                "服务未返回决策简报。"
            );
        }

        renderPlan(data.plan);

        const sourceLookup = renderEvidence(
            data.evidence || [],
            data.assessments || []
        );

        renderDecisionBrief(
            data.brief,
            sourceLookup
        );

        runMessage.textContent =
            "研究与决策简报已生成。";

        resultPanel.scrollIntoView({
            behavior: "smooth",
        });
    } catch (error) {
        errorMessage.textContent =
            error.message
            || "发生未知错误，请稍后重试。";

        errorPanel.hidden = false;

        runMessage.textContent =
            "本次研究请求未能完成。";

        errorPanel.scrollIntoView({
            behavior: "smooth",
        });
    } finally {
        window.clearInterval(progressTimer);

        runButton.disabled = false;
        runButton.textContent =
            "开始研究";
    }
});


checkBackend();

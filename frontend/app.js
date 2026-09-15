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


async function checkBackend() {
    try {
        const response = await fetch("/api/health");

        if (!response.ok) {
            throw new Error(
                "The backend returned an error."
            );
        }

        const data = await response.json();

        serviceStatus.textContent =
            `Backend status: ${data.status}`;
        statusDot.classList.add("connected");
    } catch (error) {
        serviceStatus.textContent =
            "Backend connection unavailable";
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
        plan.context || "No additional context provided.";

    horizonOutput.textContent = plan.horizon;

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

    resultStatus.textContent = "Research complete";
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
        `${sources.length} sources reviewed`;

    const sourceLookup = new Map();

    if (sources.length === 0) {
        const emptyMessage = document.createElement("p");

        emptyMessage.className = "empty-message";
        emptyMessage.textContent =
            "No sufficiently relevant evidence was found.";

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
            record.title || "Untitled source";

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
                    "Type",
                    assessment.source_type,
                    "neutral-tag"
                ),
                createTag(
                    "Quality",
                    assessment.quality,
                    `quality-${assessment.quality}`
                ),
                createTag(
                    "Relevance",
                    assessment.relevance,
                    `relevance-${assessment.relevance}`
                )
            );
        }

        const queryText = document.createElement("p");
        queryText.className = "evidence-query";
        queryText.textContent = `Search query: ${query}`;

        const claimHeading = document.createElement("h3");
        claimHeading.textContent = "Supported claim";

        const claimText = document.createElement("p");
        claimText.className = "evidence-claim";
        claimText.textContent = assessment
            ? assessment.key_claim
            : "No reviewer assessment was returned.";

        const limitationsHeading =
            document.createElement("h3");
        limitationsHeading.textContent = "Limitations";

        const limitationsText =
            document.createElement("p");
        limitationsText.className =
            "evidence-limitations";
        limitationsText.textContent = assessment
            ? assessment.limitations
            : (
                "This source has not been reviewed "
                + "and requires manual verification."
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
                "No verified source citation";

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
        `Confidence: ${confidence}`;

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
        "Running research agent...";

    const progressMessages = [
        "Building the research plan...",
        "Searching for relevant evidence...",
        "Reviewing source quality...",
        "Preparing the decision brief...",
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
                "Research request failed with "
                + `status ${response.status}.`
            );
        }

        const data = await response.json();

        if (!data.plan) {
            throw new Error(
                "The response did not contain "
                + "a research plan."
            );
        }

        if (!data.brief) {
            throw new Error(
                "The response did not contain "
                + "a decision brief."
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
            "Research and decision brief complete.";

        resultPanel.scrollIntoView({
            behavior: "smooth",
        });
    } catch (error) {
        errorMessage.textContent =
            error.message
            || "An unexpected error occurred.";

        errorPanel.hidden = false;

        runMessage.textContent =
            "The research request could not be completed.";

        errorPanel.scrollIntoView({
            behavior: "smooth",
        });
    } finally {
        window.clearInterval(progressTimer);

        runButton.disabled = false;
        runButton.textContent =
            "Run research agent";
    }
});


checkBackend();
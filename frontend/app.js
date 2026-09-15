const form = document.querySelector("#research-form");
const runButton = document.querySelector("#run-button");
const resultPanel = document.querySelector("#result-panel");
const resultStatus = document.querySelector("#result-status");

const serviceStatus = document.querySelector("#service-status");
const statusDot = document.querySelector(".status-dot");

const decisionQuestionOutput = document.querySelector(
    "#decision-question-output"
);
const contextOutput = document.querySelector("#context-output");
const horizonOutput = document.querySelector("#horizon-output");
const subquestionsOutput = document.querySelector(
    "#subquestions-output"
);
const criteriaOutput = document.querySelector("#criteria-output");


async function checkBackend() {
    try {
        const response = await fetch("/api/health");

        if (!response.ok) {
            throw new Error("The backend returned an error.");
        }

        const data = await response.json();

        serviceStatus.textContent = `Backend status: ${data.status}`;
        statusDot.classList.add("connected");
    } catch (error) {
        serviceStatus.textContent = "Backend connection unavailable";
        statusDot.classList.remove("connected");
    }
}


function renderList(element, items) {
    element.replaceChildren();

    items.forEach((item) => {
        const listItem = document.createElement("li");
        listItem.textContent = item;
        element.appendChild(listItem);
    });
}


form.addEventListener("submit", async (event) => {
    event.preventDefault();

    const requestData = {
        question: document.querySelector("#question").value.trim(),
        context: document.querySelector("#context").value.trim(),
        horizon: document.querySelector("#horizon").value,
    };

    runButton.disabled = true;
    runButton.textContent = "Building research plan...";
    resultPanel.hidden = true;

    try {
        const response = await fetch("/api/research", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify(requestData),
        });

        if (!response.ok) {
            throw new Error(
                `Research request failed with status ${response.status}.`
            );
        }

        const data = await response.json();
        const plan = data.plan;

        resultStatus.textContent = "Planning complete";
        decisionQuestionOutput.textContent = plan.decision_question;
        contextOutput.textContent = plan.context;
        horizonOutput.textContent = plan.horizon;

        renderList(subquestionsOutput, plan.subquestions);
        renderList(criteriaOutput, plan.success_criteria);

        resultPanel.hidden = false;
        resultPanel.scrollIntoView({ behavior: "smooth" });
    } catch (error) {
        resultStatus.textContent = "Request failed";
        decisionQuestionOutput.textContent = error.message;
        contextOutput.textContent = "No result available.";
        horizonOutput.textContent = "—";

        renderList(subquestionsOutput, []);
        renderList(criteriaOutput, []);

        resultPanel.hidden = false;
    } finally {
        runButton.disabled = false;
        runButton.textContent = "Run research agent";
    }
});


checkBackend();
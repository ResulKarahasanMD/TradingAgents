import SwiftUI

struct ExecutionDashboardView: View {
    @Bindable var model: AppModel

    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            summaryStrip

            HStack(spacing: 16) {
                AgentStatusView(model: model)
                ActivityFeedView(model: model)
                ReportView(model: model)
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
        }
        .padding(20)
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
        .background(
            LinearGradient(
                colors: [Color(nsColor: .windowBackgroundColor), Color.blue.opacity(0.06)],
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            )
        )
    }

    private var summaryStrip: some View {
        HStack(alignment: .top, spacing: 16) {
            SummaryCard(
                title: "Run State",
                lines: [
                    model.statusLine,
                    model.isRunning ? "The Python bridge is streaming live updates." : "Ready for a new analysis.",
                ]
            )

            SummaryCard(
                title: "Decision",
                lines: [
                    model.decision ?? "No final decision yet.",
                    model.snapshot.map { "\($0.reportsCompleted)/\($0.reportsTotal) report stages complete" } ?? "No progress data yet.",
                ]
            )

            SummaryCard(
                title: "Usage",
                lines: usageLines
            )

            SummaryCard(
                title: "Outputs",
                lines: [
                    model.resultsDirectoryPath ?? "Results directory not created yet.",
                    model.reportFilePath ?? "Complete report not generated yet.",
                ]
            )
        }
    }

    private var usageLines: [String] {
        guard let stats = model.snapshot?.stats else {
            return ["No stats yet.", "LLM and tool counts appear here once the run starts."]
        }

        return [
            "LLM calls: \(stats.llmCalls) | Tool calls: \(stats.toolCalls)",
            "Tokens: \(stats.tokensIn) in / \(stats.tokensOut) out | \(elapsedText)",
        ]
    }

    private var elapsedText: String {
        guard let elapsed = model.snapshot?.elapsedSeconds else {
            return "00:00"
        }
        let total = Int(elapsed)
        return String(format: "%02d:%02d", total / 60, total % 60)
    }
}

private struct SummaryCard: View {
    let title: String
    let lines: [String]

    var body: some View {
        GroupBox(title) {
            VStack(alignment: .leading, spacing: 6) {
                ForEach(lines, id: \.self) { line in
                    Text(line)
                        .font(.callout)
                        .foregroundStyle(.primary)
                        .textSelection(.enabled)
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            .frame(minHeight: 72, alignment: .topLeading)
        }
        .frame(maxWidth: .infinity)
    }
}

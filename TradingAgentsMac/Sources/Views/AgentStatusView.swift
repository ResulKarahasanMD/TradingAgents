import SwiftUI

struct AgentStatusView: View {
    @Bindable var model: AppModel

    var body: some View {
        GroupBox("Agents") {
            ScrollView {
                VStack(alignment: .leading, spacing: 14) {
                    if let snapshot = model.snapshot {
                        ForEach(model.agentTeams, id: \.name) { team in
                            let visibleAgents = team.agents.filter { snapshot.agentStatuses[$0] != nil }
                            if !visibleAgents.isEmpty {
                                VStack(alignment: .leading, spacing: 8) {
                                    Text(team.name)
                                        .font(.headline)
                                    ForEach(visibleAgents, id: \.self) { agent in
                                        HStack {
                                            Circle()
                                                .fill(statusColor(snapshot.agentStatuses[agent] ?? "pending"))
                                                .frame(width: 10, height: 10)
                                            Text(agent)
                                            Spacer()
                                            Text(snapshot.agentStatuses[agent] ?? "pending")
                                                .foregroundStyle(.secondary)
                                        }
                                        .font(.callout)
                                    }
                                }
                                Divider()
                            }
                        }
                    } else {
                        Text("Agent progress appears here once the bridge starts streaming snapshots.")
                            .foregroundStyle(.secondary)
                            .frame(maxWidth: .infinity, alignment: .leading)
                    }
                }
                .frame(maxWidth: .infinity, alignment: .leading)
            }
        }
        .frame(maxWidth: 280)
    }

    private func statusColor(_ status: String) -> Color {
        switch status {
        case "completed":
            return .green
        case "in_progress":
            return .blue
        case "error":
            return .red
        default:
            return .orange
        }
    }
}

import SwiftUI

struct ActivityFeedView: View {
    @Bindable var model: AppModel

    var body: some View {
        GroupBox("Activity") {
            ScrollView {
                VStack(alignment: .leading, spacing: 14) {
                    if let error = model.runError {
                        Text(error)
                            .foregroundStyle(.red)
                            .textSelection(.enabled)
                    }

                    if let snapshot = model.snapshot {
                        if !snapshot.messages.isEmpty {
                            SectionHeader(title: "Messages")
                            ForEach(snapshot.messages.reversed()) { entry in
                                VStack(alignment: .leading, spacing: 4) {
                                    Text("\(entry.timestamp) · \(entry.kind)")
                                        .font(.caption)
                                        .foregroundStyle(.secondary)
                                    Text(entry.content)
                                        .font(.callout)
                                        .textSelection(.enabled)
                                }
                                Divider()
                            }
                        }

                        if !snapshot.toolCalls.isEmpty {
                            SectionHeader(title: "Tool Calls")
                            ForEach(snapshot.toolCalls.reversed()) { tool in
                                VStack(alignment: .leading, spacing: 4) {
                                    Text("\(tool.timestamp) · \(tool.name)")
                                        .font(.caption)
                                        .foregroundStyle(.secondary)
                                    Text(tool.formattedArgs)
                                        .font(.system(.callout, design: .monospaced))
                                        .textSelection(.enabled)
                                }
                                Divider()
                            }
                        }
                    } else {
                        Text("The live message feed will appear here.")
                            .foregroundStyle(.secondary)
                    }

                    if !model.diagnostics.isEmpty {
                        SectionHeader(title: "Diagnostics")
                        ForEach(Array(model.diagnostics.enumerated()), id: \.offset) { _, diagnostic in
                            Text(diagnostic)
                                .font(.system(.caption, design: .monospaced))
                                .foregroundStyle(.secondary)
                                .textSelection(.enabled)
                            Divider()
                        }
                    }
                }
                .frame(maxWidth: .infinity, alignment: .leading)
            }
        }
        .frame(maxWidth: .infinity)
    }
}

private struct SectionHeader: View {
    let title: String

    var body: some View {
        Text(title)
            .font(.headline)
            .padding(.bottom, 2)
    }
}

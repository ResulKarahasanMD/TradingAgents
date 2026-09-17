import SwiftUI

struct ReportView: View {
    @Bindable var model: AppModel

    var body: some View {
        GroupBox("Reports") {
            VStack(alignment: .leading, spacing: 12) {
                HStack {
                    Button("Open Report") {
                        model.openReportFile()
                    }
                    .disabled(model.reportFilePath == nil)

                    Button("Open Results") {
                        model.openResultsDirectory()
                    }
                    .disabled(model.resultsDirectoryPath == nil)

                    Spacer()
                }

                ScrollView {
                    Text(reportText)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .font(.system(.body, design: .default))
                        .textSelection(.enabled)
                }
            }
        }
        .frame(maxWidth: .infinity)
    }

    private var reportText: String {
        if let finalReport = model.snapshot?.finalReportMarkdown, !finalReport.isEmpty {
            return finalReport
        }
        if let currentReport = model.snapshot?.currentReportMarkdown, !currentReport.isEmpty {
            return currentReport
        }
        return "The latest report section and final report render here as the Python bridge produces them."
    }
}

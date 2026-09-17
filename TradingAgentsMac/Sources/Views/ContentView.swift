import SwiftUI
import UniformTypeIdentifiers

private enum FolderPickerTarget {
    case workspace
    case results
}

struct ContentView: View {
    @Bindable var model: AppModel
    @State private var folderPickerTarget: FolderPickerTarget?

    var body: some View {
        NavigationSplitView {
            ConfigurationSidebarView(
                model: model,
                chooseWorkspace: { folderPickerTarget = .workspace },
                chooseResultsRoot: { folderPickerTarget = .results }
            )
            .navigationSplitViewColumnWidth(min: 320, ideal: 360)
        } detail: {
            ExecutionDashboardView(model: model)
        }
        .navigationSplitViewStyle(.balanced)
        .toolbar {
            ToolbarItemGroup {
                Button {
                    model.loadCatalog()
                } label: {
                    Label("Reload", systemImage: "arrow.clockwise")
                }
                .disabled(model.isLoadingCatalog || model.isRunning)

                Button {
                    model.openResultsDirectory()
                } label: {
                    Label("Results", systemImage: "folder")
                }
                .disabled(model.resultsDirectoryPath == nil)

                if model.isRunning {
                    Button(role: .destructive) {
                        model.cancelAnalysis()
                    } label: {
                        Label("Cancel", systemImage: "stop.fill")
                    }
                } else {
                    Button {
                        model.startAnalysis()
                    } label: {
                        Label("Run Analysis", systemImage: "play.fill")
                    }
                    .disabled(!model.canStart)
                }
            }
        }
        .fileImporter(
            isPresented: Binding(
                get: { folderPickerTarget != nil },
                set: { if !$0 { folderPickerTarget = nil } }
            ),
            allowedContentTypes: [.folder],
            allowsMultipleSelection: false
        ) { result in
            defer { folderPickerTarget = nil }
            guard case .success(let urls) = result, let url = urls.first else { return }
            switch folderPickerTarget {
            case .workspace:
                model.workspacePath = url.path
                if model.resultsRootPath.hasSuffix("/results") {
                    model.resultsRootPath = url.appending(path: "results", directoryHint: .isDirectory).path
                }
                model.loadCatalog()
            case .results:
                model.resultsRootPath = url.path
            case .none:
                break
            }
        }
        .task {
            model.loadCatalogIfNeeded()
        }
    }
}

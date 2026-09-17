import SwiftUI

struct ConfigurationSidebarView: View {
    @Bindable var model: AppModel
    let chooseWorkspace: () -> Void
    let chooseResultsRoot: () -> Void

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 18) {
                workspaceSection
                marketSection
                analystSection
                providerSection
                if let validationMessage = model.validationMessage {
                    Text(validationMessage)
                        .font(.callout)
                        .foregroundStyle(.orange)
                }
            }
            .padding(16)
        }
        .background(.regularMaterial)
    }

    private var workspaceSection: some View {
        GroupBox("Workspace") {
            VStack(alignment: .leading, spacing: 10) {
                TextField("Repository root", text: $model.workspacePath)
                    .textFieldStyle(.roundedBorder)

                TextField("Results directory", text: $model.resultsRootPath)
                    .textFieldStyle(.roundedBorder)

                HStack {
                    Button("Choose Repo…", action: chooseWorkspace)
                    Button("Choose Results…", action: chooseResultsRoot)
                    Spacer()
                    Button("Reload Options") {
                        model.loadCatalog()
                    }
                    .disabled(model.isLoadingCatalog)
                }

                Text("The app launches `uv run python -m cli.macos_bridge` inside this workspace.")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
        }
    }

    private var marketSection: some View {
        GroupBox("Analysis Setup") {
            VStack(alignment: .leading, spacing: 12) {
                TextField("Ticker", text: $model.ticker)
                    .textFieldStyle(.roundedBorder)

                DatePicker("Analysis Date", selection: $model.analysisDate, displayedComponents: .date)

                Picker("Research Depth", selection: $model.researchDepth) {
                    ForEach(model.catalog?.researchDepths ?? []) { option in
                        Text(option.label).tag(option.value)
                    }
                }
                .pickerStyle(.segmented)

                Picker("Output Language", selection: $model.outputLanguage) {
                    ForEach(model.catalog?.outputLanguages ?? []) { option in
                        Text(option.label).tag(option.value)
                    }
                }

                if model.outputLanguage == "custom" {
                    TextField("Custom language", text: $model.customOutputLanguage)
                        .textFieldStyle(.roundedBorder)
                }
            }
        }
    }

    private var analystSection: some View {
        GroupBox("Analyst Team") {
            VStack(alignment: .leading, spacing: 12) {
                ForEach(model.catalog?.analysts ?? []) { analyst in
                    Toggle(
                        isOn: Binding(
                            get: { model.selectedAnalysts.contains(analyst.value) },
                            set: { model.setAnalyst(analyst.value, enabled: $0) }
                        )
                    ) {
                        VStack(alignment: .leading, spacing: 2) {
                            Text(analyst.title)
                            Text(analyst.summary)
                                .font(.caption)
                                .foregroundStyle(.secondary)
                        }
                    }
                    .toggleStyle(.checkbox)
                }
            }
        }
    }

    private var providerSection: some View {
        GroupBox("LLM Provider") {
            VStack(alignment: .leading, spacing: 12) {
                Picker("Provider", selection: $model.provider) {
                    ForEach(model.catalog?.providers ?? []) { provider in
                        Text(provider.name).tag(provider.value)
                    }
                }
                .onChange(of: model.provider) { _, _ in
                    model.providerDidChange()
                }

                TextField("Backend URL", text: $model.backendURL)
                    .textFieldStyle(.roundedBorder)

                if model.supportsCustomModels {
                    TextField("Quick model ID", text: $model.customQuickModel)
                        .textFieldStyle(.roundedBorder)
                    TextField("Deep model ID", text: $model.customDeepModel)
                        .textFieldStyle(.roundedBorder)
                } else {
                    Picker("Quick model", selection: $model.quickModel) {
                        ForEach(model.availableQuickModels) { option in
                            Text(option.label).tag(option.value)
                        }
                    }
                    Picker("Deep model", selection: $model.deepModel) {
                        ForEach(model.availableDeepModels) { option in
                            Text(option.label).tag(option.value)
                        }
                    }
                }

                switch model.provider {
                case "openai":
                    Picker("Reasoning Effort", selection: $model.openAIReasoningEffort) {
                        ForEach(model.catalog?.openAIReasoningEfforts ?? []) { option in
                            Text(option.label).tag(option.value)
                        }
                    }
                case "anthropic":
                    Picker("Effort", selection: $model.anthropicEffort) {
                        ForEach(model.catalog?.anthropicEfforts ?? []) { option in
                            Text(option.label).tag(option.value)
                        }
                    }
                case "google":
                    Picker("Thinking Mode", selection: $model.googleThinkingLevel) {
                        ForEach(model.catalog?.googleThinkingLevels ?? []) { option in
                            Text(option.label).tag(option.value)
                        }
                    }
                default:
                    EmptyView()
                }
            }
        }
    }
}

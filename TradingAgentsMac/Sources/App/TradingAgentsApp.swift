import SwiftUI

@main
struct TradingAgentsApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) private var appDelegate
    @State private var model = AppModel()

    var body: some Scene {
        WindowGroup("TradingAgents") {
            ContentView(model: model)
                .frame(minWidth: 1280, minHeight: 840)
        }
        .commands {
            SidebarCommands()
            CommandGroup(replacing: .newItem) { }
        }
    }
}

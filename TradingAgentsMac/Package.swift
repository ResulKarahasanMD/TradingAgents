// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "TradingAgentsMac",
    platforms: [
        .macOS(.v14),
    ],
    products: [
        .executable(
            name: "TradingAgents",
            targets: ["TradingAgentsApp"]
        ),
    ],
    targets: [
        .executableTarget(
            name: "TradingAgentsApp",
            path: "Sources"
        ),
    ]
)

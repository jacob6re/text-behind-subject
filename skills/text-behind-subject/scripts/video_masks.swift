import Foundation
import AVFoundation
import Vision
import CoreImage
import ImageIO
import UniformTypeIdentifiers

// Input is already upright, CFR, SDR. One PNG per decoded frame, in frame order.
do {
    let a = CommandLine.arguments
    guard a.count == 5 else { throw NSError(domain: "Usage: video_masks input.mp4 output-dir width height", code: 1) }
    let asset = AVURLAsset(url: URL(fileURLWithPath: a[1]))
    guard let track = asset.tracks(withMediaType: .video).first else { throw NSError(domain: "No video", code: 2) }
    let reader = try AVAssetReader(asset: asset)
    let output = AVAssetReaderTrackOutput(track: track, outputSettings: [kCVPixelBufferPixelFormatTypeKey as String: kCVPixelFormatType_32BGRA])
    reader.add(output)
    let request = VNGeneratePersonSegmentationRequest()
    request.qualityLevel = .accurate
    request.outputPixelFormat = kCVPixelFormatType_OneComponent8
    let sequence = VNSequenceRequestHandler()
    let context = CIContext()
    let width = Int(a[3])!, height = Int(a[4])!
    try FileManager.default.createDirectory(atPath: a[2], withIntermediateDirectories: true)
    guard reader.startReading() else { throw reader.error! }
    var count = 0
    while let sample = output.copyNextSampleBuffer() {
        guard let buffer = CMSampleBufferGetImageBuffer(sample) else { throw NSError(domain: "Missing frame", code: 3) }
        try sequence.perform([request], on: buffer)
        guard let mask = request.results?.first?.pixelBuffer else { throw NSError(domain: "Missing person mask", code: 4) }
        let image = CIImage(cvPixelBuffer: mask)
        let scaled = image.transformed(by: CGAffineTransform(scaleX: Double(width)/image.extent.width, y: Double(height)/image.extent.height))
        guard let cg = context.createCGImage(scaled, from: CGRect(x: 0,y: 0,width: width,height: height)),
              let dest = CGImageDestinationCreateWithURL(URL(fileURLWithPath: a[2]+String(format: "/%06d.png", count)) as CFURL, UTType.png.identifier as CFString, 1, nil) else { throw NSError(domain: "Mask export failed", code: 5) }
        CGImageDestinationAddImage(dest, cg, nil)
        guard CGImageDestinationFinalize(dest) else { throw NSError(domain: "PNG write failed", code: 6) }
        count += 1
        if count % 30 == 0 { print("masks: \(count)"); fflush(stdout) }
    }
    guard reader.status == .completed else { throw reader.error ?? NSError(domain: "Reader failed",code: 7) }
    print("completed \(count) masks")
} catch { fputs("\(error)\n", stderr); exit(1) }

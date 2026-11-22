# Experimental iOS link kit

This prototype is not wired into deployment. It requires the app's own fresh
production build receipt and full native build; it does not yet replace Cargo or
prove that a kit downloaded from a remote publisher is authentic.

Capture one normal iOS device production build with the pinned Exact SDK. Find
the Xcode `XCBuildData/*.xcbuilddata/manifest.json` containing the `ExactIOS`
link, the SDK's production bake and receipt, and its captured Rust archive.
From this repository's root:

```sh
python3 .github/actions/exact-setup/scripts/ios-link-kit-capture.py \
  --manifest "$XCODE_MANIFEST" --receipt "$RECEIPT" --bake "$BAKE" \
  --archive "$RUST_ARCHIVE" --out "$CAPTURE"
python3 .github/actions/exact-setup/scripts/ios-link-kit.py create \
  --proof "$CAPTURE" --kit "$KIT" --receipt "$RECEIPT" \
  --bake "$BAKE" --app "$APP"
python3 .github/actions/exact-setup/scripts/ios-link-kit.py link \
  --kit "$KIT" --out "$NEW_EXECUTABLE" --receipt "$FRESH_RECEIPT" \
  --bake "$FRESH_BAKE" --app "$APP"
```

A local experiment applies `ios-link-kit-test-hook.patch` to an isolated Exact
checkout. It tries the link after the SDK's own Cargo build and receipt and
falls back to the ordinary Swift build on refusal. Exact's normal identity,
capability, signing, and archive code then runs. The patch is not a supported
SDK integration and must not be applied to production builds as-is.

Before deploying, a supported Exact hook must retain and validate actual Cargo
compiler and build-script evidence for a fresh receipt without Cargo; the kit
and its command must have authenticated provenance; source and feature gates
need independent review and broader negative tests; and actual installed app,
update, and replacement flows must be verified. Exact must own its packaging
and receipt checks throughout.

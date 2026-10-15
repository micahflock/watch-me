// Diag -- release/debug stub. The on-wrist diagnostic readout lives in
// faces/two-worlds-v2/diag/Diag.mc and only compiles into the diag build
// (scripts/build.sh two-worlds-v2 --diag); here every hook is a no-op so the
// shipped face pays nothing for it.
module Diag {
    function wrapGrove(grove) { return grove; }
    function component() { return null; }
    function save(grove) {}
}

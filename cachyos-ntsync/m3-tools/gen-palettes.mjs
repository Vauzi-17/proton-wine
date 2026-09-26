import { Hct, SchemeTonalSpot, MaterialDynamicColors, hexFromArgb, argbFromHex } from '@material/material-color-utilities';
const seeds = { purple:'#6750A4', blue:'#1A73E8', teal:'#00897B', green:'#43A047', orange:'#F57C00', pink:'#D81B60' };
const roles = ['primary','onPrimary','primaryContainer','onPrimaryContainer','secondary','onSecondary','secondaryContainer','onSecondaryContainer','tertiary','tertiaryContainer','onTertiaryContainer','error','onError','errorContainer','onErrorContainer','surface','onSurface','surfaceVariant','onSurfaceVariant','surfaceDim','surfaceBright','surfaceContainerLowest','surfaceContainerLow','surfaceContainer','surfaceContainerHigh','surfaceContainerHighest','inverseSurface','inverseOnSurface','inversePrimary','outline','outlineVariant','shadow','scrim'];
const out = {};
for (const [name, hex] of Object.entries(seeds)) {
  out[name] = { seed: hex };
  for (const dark of [false, true]) {
    const s = new SchemeTonalSpot(Hct.fromInt(argbFromHex(hex)), dark, 0.0);
    const m = {};
    for (const r of roles) {
      const dc = MaterialDynamicColors[r];
      if (!dc) { m[r] = null; continue; }
      m[r] = hexFromArgb(dc.getArgb(s));
    }
    out[name][dark ? 'dark' : 'light'] = m;
  }
}
console.log(JSON.stringify(out, null, 1));

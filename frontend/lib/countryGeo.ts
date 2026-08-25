/**
 * UI-only lookup between the Korean country names returned by the API
 * (country_profile_base.csv 등) and the ISO-3166-1 numeric id used as the
 * feature `id` in public/countries-50m.json (Natural Earth / world-atlas).
 * This is a display mapping, not a data transformation — no indicator
 * values are derived here.
 */
export const COUNTRY_NAME_TO_GEO_ID: Record<string, string> = {
  중국: "156",
  일본: "392",
  대만: "158",
  미국: "840",
  필리핀: "608",
  베트남: "704",
  싱가포르: "702",
  인도네시아: "360",
  태국: "764",
  말레이시아: "458",
  캐나다: "124",
  호주: "036",
  러시아: "643",
  인도: "356",
  프랑스: "250",
  독일: "276",
  영국: "826",
  멕시코: "484",
  카자흐스탄: "398",
  튀르키예: "792",
  브라질: "076",
  사우디아라비아: "682",
  UAE: "784",
};

export const GEO_ID_TO_COUNTRY_NAME: Record<string, string> = Object.fromEntries(
  Object.entries(COUNTRY_NAME_TO_GEO_ID).map(([name, id]) => [id, name]),
);

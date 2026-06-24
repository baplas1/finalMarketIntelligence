import pandas as pd
import os
import glob
import re



folder_path = "./csv_folder"

bridge_terms = [
    "bridge",
    "bridges",
    "culvert",
    "culverts",
    "overpass",
    "overpasses",
    "underpass",
    "underpasses",
    "viaduct",
    "viaducts",
    "deck",
    "decks",
    "bridge deck",
    "bridge beam",
    "bridge beams",
    "abutment",
    "abutments",
    "pier",
    "piers",
    "wingwall",
    "wingwalls",
    "headwall",
    "headwalls",
    "bearing",
    "bearings",
    "bridge bearing",
    "bridge bearings",
    "expansion joint",
    "expansion joints",
    "parapet",
    "bridge rail",
    "bridge barrier",
    "traffic barrier",
    "retaining wall",
    "retaining walls",
    "grade separation",
    "river crossing",
    "stream crossing",
    "watercourse crossing",
    "highway structure",
    "highway structures",
    "transportation structure",
    "transportation structures",
]

activity = [
    "inspection",
    "inspections",
    "design",
    "designs",
    "detailed design",
    "preliminary design",
    "analysis",
    "analyses",
    "assessment",
    "assessments",
    "condition assessment",
    "condition assessments",
    "structural assessment",
    "structural assessments",
    "engineering assessment",
    "engineering assessments",
    "evaluation",
    "evaluations",
    "load rating",
    "load ratings",
    "load evaluation",
    "load evaluations",
    "review",
    "reviews",
    "peer review",
    "peer reviews",
    "investigation",
    "investigations",
    "field investigation",
    "field investigations",
    "site investigation",
    "site investigations",
    "rehabilitation",
    "rehabilitations",
    "rehabilitate",
    "retrofit",
    "retrofits",
    "seismic retrofit",
    "seismic retrofits",
    "seismic assessment",
    "seismic assessments",
    "seismic upgrade",
    "seismic upgrades",
    "replacement",
    "replacements",
    "upgrade",
    "upgrades",
    "renewal",
    "renewals",
    "strengthening",
    "monitoring",
    "monitorings",
    "structural health monitoring",
    "maintenance",
    "maintenances",
    "feasibility study",
    "feasibility studies",
    "engineering study",
    "engineering studies",
    "contract administration",
    "contract administrations",
    "construction administration",
    "construction administrations",
    "construction supervision",
    "construction supervisions",
]

category = [
    "Professional engineering services",
    "Engineering services",
    "Civil engineering",
    "Structural engineering",
    "Transportation engineering",
    "Consulting engineering",
    "Engineering consulting",
    "Engineering and design services"
]

# search_terms_work_desc = [
#     "bridge",
#     "culvert",
#     "deck",
#     "seismic retrofit",
#     "structural inspection",
#     "overpass",
#     "bridges",
#     "culverts",
#     "decks",
#     "structural inspections",
#     "bridge inspection",

# ]

escaped_terms = [re.escape(term) for term in bridge_terms]


bridge_terms_pattern = r"\b(?:{})\b".format(
    "|".join(re.escape(term) for term in bridge_terms)
)

category_pattern = r"\b(?:{})\b".format(
    "|".join(re.escape(term) for term in category)
)

activity_pattern = r"\b(?:{})\b".format(
    "|".join(re.escape(term) for term in activity)
)

def normalize_columns(columns):
    return [str(col).strip().lower() for col in columns]


def find_best_column(columns, candidates):
    for candidate in candidates:
        if candidate in columns:
            return candidate
    return None


def get_unique_matches(text, regex):
    matches = regex.findall(str(text))
    seen = set()
    ordered = []
    for match in matches:
        term = match.strip().lower()
        if term and term not in seen:
            seen.add(term)
            ordered.append(term)
    return ordered

all_filtered_dfs = []

for file_path in glob.glob(os.path.join(folder_path, "*.csv")):

    print(f"Processing: {file_path}")

    try:
        df = pd.read_csv(file_path, encoding="utf-8", low_memory=False)
    except UnicodeDecodeError:
        df = pd.read_csv(file_path, encoding="latin1", low_memory=False)




    df = df.loc[:, ~df.columns.str.contains("fra", case=False, na=False)]
    df.columns = normalize_columns(df.columns)

    if 'column_map' not in globals():
        column_map = {
            'Project Title': find_best_column(
                df.columns,
                ['title-titre-eng', 'title-titre-fra', 'title', 'title-titre']
            ),
            'Award Date': find_best_column(
                df.columns,
                [
                    'contractawarddate-dateattributioncontrat',
                    'publicationdate-datepublication',
                    'contractstartdate-contratdatedebut',
                    'contractenddate-datefincontrat'
                ]
            ),
            'Successful Vendor': find_best_column(
                df.columns,
                [
                    'supplierlegalname-nomlegalfournisseur-eng',
                    'supplierstandardizedname-nomnormalisefournisseur-eng',
                    'supplieroperatingname-nomcommercialfournisseur-eng'
                ]
            ),
            'Issued by Organization': find_best_column(
                df.columns,
                ['contractingentityname-nomentitcontractante-eng']
            ),
            'Issued for Organization': find_best_column(
                df.columns,
                ['enduserentitiesname-nomentitesutilisateurfinal-eng']
            ),
            'Award Total': find_best_column(
                df.columns,
                ['totalcontractvalue-valeurtotalcontrat', 'contractamount-montantcontrat']
            ),
        }


    # for col in df.select_dtypes(include=["object", "string"]):
    #     try:
    #         df[col] = (
    #         df[col]
    #         .astype(str)
    #         .str.encode("cp1252")
    #         .str.decode("utf-8")
    #         )
    #     except:
    #         pass 



    # Filter by work description
    filtered_by_desc_of_work = df[
        (df["tenderdescription-descriptionappeloffres-eng"]
        .astype(str)
        .str.contains(bridge_terms_pattern, case=False, na=False)  &
         df["unspscdescription-eng"]
        .astype(str)
        .str.contains(category_pattern, case=False, na=False)) 
        
        |

        (df["tenderdescription-descriptionappeloffres-eng"]
        .astype(str)
        .str.contains(bridge_terms_pattern, case=False, na=False)  &
         df["tenderdescription-descriptionappeloffres-eng"]
        .astype(str)
        .str.contains(activity_pattern, case=False, na=False))
    ]

    # Optional: keep track of source file
    filtered_by_desc_of_work["source_file"] = os.path.basename(file_path)

    output_df = pd.DataFrame()
    output_df["Data Source"] = filtered_by_desc_of_work["source_file"]
    output_df["Project Title"] = (
        filtered_by_desc_of_work[column_map['Project Title']]
        if column_map['Project Title'] in filtered_by_desc_of_work.columns
        else ""
    )
    output_df["Tender Description"] = (
        filtered_by_desc_of_work["tenderdescription-descriptionappeloffres-eng"]
        if "tenderdescription-descriptionappeloffres-eng" in filtered_by_desc_of_work.columns
        else ""
    )

    work_desc_source = 'tenderdescription-descriptionappeloffres-eng'
    bridge_regex = re.compile(bridge_terms_pattern, flags=re.IGNORECASE)
    activity_regex = re.compile(activity_pattern, flags=re.IGNORECASE)
    output_df["Work Type"] = [
        "; ".join(
            get_unique_matches(title, bridge_regex)
            + get_unique_matches(title, activity_regex)
        )
        for title in filtered_by_desc_of_work[work_desc_source].astype(str)
    ]

    output_df["Award Date"] = (
        filtered_by_desc_of_work[column_map['Award Date']]
        if column_map['Award Date'] in filtered_by_desc_of_work.columns
        else ""
    )
    output_df["Successful Vendor"] = (
        filtered_by_desc_of_work[column_map['Successful Vendor']]
        if column_map['Successful Vendor'] in filtered_by_desc_of_work.columns
        else ""
    )
    output_df["Issued by Organization"] = (
        filtered_by_desc_of_work[column_map['Issued by Organization']]
        if column_map['Issued by Organization'] in filtered_by_desc_of_work.columns
        else ""
    )
    output_df["Issued for Organization"] = (
        filtered_by_desc_of_work[column_map['Issued for Organization']]
        if column_map['Issued for Organization'] in filtered_by_desc_of_work.columns
        else ""
    )
    output_df["Award Total"] = (
        filtered_by_desc_of_work[column_map['Award Total']]
        if column_map['Award Total'] in filtered_by_desc_of_work.columns
        else ""
    )

    # Add to list
    all_filtered_dfs.append(output_df)



final_df = pd.concat(all_filtered_dfs, ignore_index=True)

# final_df = final_df.drop(columns=["referenceNumber-numeroReference"])
# final_df = final_df.drop(columns=["amendmentNumber-numeroModification"])
# final_df = final_df.drop(columns=["procurementNumber-numeroApprovisionnement"])
# final_df = final_df.drop(columns=["solicitationNumber-numeroSollicitation"])
# final_df = final_df.drop(columns=["contractNumber-numeroContrat"])
# final_df = final_df.drop(columns=["numberOfRecords-nombreEnregistrements"])
# final_df = final_df.drop(columns=["contractStatus-statutContrat-eng"])
# final_df = final_df.drop(columns=["instrumentType-typeInstrument-eng"])
# final_df = final_df.drop(columns=["amendmentType-typeModification-eng"])

# final_df = final_df.drop(columns=["gsin-nibs"])
# final_df = final_df.drop(columns=["gsinDescription-nibsDescription-eng"])
# final_df = final_df.drop(columns=["numberOfRecords-nombreEnregistrements"])
# final_df = final_df.drop(columns=["contractStatus-statutContrat-eng"])
# final_df = final_df.drop(columns=["instrumentType-typeInstrument-eng"])
# final_df = final_df.drop(columns=["amendmentType-typeModification-eng"])

# Combined output is kept in memory; the main pipeline writes only the final workbook.




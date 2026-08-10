from wv.ml.speciesnet_worker import _semantic_label


def test_semantic_label_maps_speciesnet_special_taxa():
    assert _semantic_label({"taxon_id": "f1856211-cfb7-4a5b-9158-c0f72fd09ee6"}) == "blank"
    assert _semantic_label({"taxon_id": "990ae9dd-7a59-4344-afcb-1b7b21368000"}) == "human"
    assert _semantic_label({"taxon_id": "e2895ed5-780b-48f6-8a11-9e27cb594511"}) == "vehicle"
    assert _semantic_label({"taxon_id": "f2efdae9-efb8-48fb-8a91-eccf79ab4ffb"}) == "other"


def test_semantic_label_maps_taxonomic_result_to_animal():
    assert _semantic_label({"taxon_id": "taxon-id"}) == "animal"

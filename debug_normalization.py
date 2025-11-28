from search.normalizer import TextNormalizer
from search.similarity import SimilarityCalculator

norm = TextNormalizer()
sim = SimilarityCalculator()

city = "Київ,"
normalized = norm.normalize_city(city)
print(f"Original: '{city}'")
print(f"Normalized: '{normalized}'")
print(f"Is Kyiv? {normalized in ['київ', 'м.київ', 'м. київ']}")

street1 = "бул.Л.Українки"
street2 = "бульв. Лесі Українки"
n1 = norm.normalize_street(street1)
n2 = norm.normalize_street(street2)
print(f"\nStreet 1: '{street1}' -> '{n1}'")
print(f"Street 2: '{street2}' -> '{n2}'")

score = sim.token_similarity(n1, n2)
print(f"Similarity: {score}")

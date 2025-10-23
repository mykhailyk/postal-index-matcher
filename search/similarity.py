"""
Алгоритми для обчислення схожості тексту
"""
from typing import Tuple


class SimilarityCalculator:
    """Клас для обчислення схожості між текстами"""
    
    @staticmethod
    def jaro_winkler_similarity(s1: str, s2: str, scaling: float = 0.1) -> float:
        """
        Jaro-Winkler схожість
        Добре працює для коротких рядків та українських назв
        
        Args:
            s1: Перший рядок
            s2: Другий рядок
            scaling: Коефіцієнт для префікса (0.1 стандартно)
            
        Returns:
            Схожість від 0.0 до 1.0
        """
        if not s1 or not s2:
            return 0.0
        
        s1, s2 = s1.lower(), s2.lower()
        
        if s1 == s2:
            return 1.0
        
        # Jaro distance
        jaro = SimilarityCalculator._jaro_similarity(s1, s2)
        
        if jaro < 0.7:
            return jaro
        
        # Winkler modification - бонус за спільний префікс
        prefix = 0
        max_prefix = min(len(s1), len(s2), 4)
        
        for i in range(max_prefix):
            if s1[i] == s2[i]:
                prefix += 1
            else:
                break
        
        return jaro + (prefix * scaling * (1 - jaro))
    
    @staticmethod
    def _jaro_similarity(s1: str, s2: str) -> float:
        """Базовий Jaro distance"""
        len1, len2 = len(s1), len(s2)
        
        if len1 == 0 or len2 == 0:
            return 0.0
        
        # Match window
        match_window = max(len1, len2) // 2 - 1
        match_window = max(0, match_window)
        
        s1_matches = [False] * len1
        s2_matches = [False] * len2
        
        matches = 0
        transpositions = 0
        
        # Знаходимо співпадіння
        for i in range(len1):
            start = max(0, i - match_window)
            end = min(i + match_window + 1, len2)
            
            for j in range(start, end):
                if s2_matches[j] or s1[i] != s2[j]:
                    continue
                s1_matches[i] = s2_matches[j] = True
                matches += 1
                break
        
        if matches == 0:
            return 0.0
        
        # Рахуємо транспозиції
        k = 0
        for i in range(len1):
            if not s1_matches[i]:
                continue
            while not s2_matches[k]:
                k += 1
            if s1[i] != s2[k]:
                transpositions += 1
            k += 1
        
        jaro = (
            matches / len1 +
            matches / len2 +
            (matches - transpositions / 2) / matches
        ) / 3
        
        return jaro
    
    @staticmethod
    def levenshtein_distance(s1: str, s2: str) -> int:
        """
        Відстань Левенштейна
        Кількість операцій для перетворення s1 в s2
        
        Args:
            s1: Перший рядок
            s2: Другий рядок
            
        Returns:
            Відстань (чим менше, тим схожіші)
        """
        if not s1:
            return len(s2)
        if not s2:
            return len(s1)
        
        if len(s1) < len(s2):
            return SimilarityCalculator.levenshtein_distance(s2, s1)
        
        previous_row = list(range(len(s2) + 1))
        
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                # Вартість операцій
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row
        
        return previous_row[-1]
    
    @staticmethod
    def levenshtein_similarity(s1: str, s2: str) -> float:
        """
        Нормалізована схожість Левенштейна (0.0 - 1.0)
        """
        if not s1 or not s2:
            return 0.0
        
        distance = SimilarityCalculator.levenshtein_distance(s1.lower(), s2.lower())
        max_len = max(len(s1), len(s2))
        
        if max_len == 0:
            return 1.0
        
        return 1.0 - (distance / max_len)
    
    @staticmethod
    def consonant_similarity(s1: str, s2: str, consonants1: str, consonants2: str) -> float:
        """
        Схожість по приголосним літерам
        Стійка до помилок у голосних
        
        Args:
            s1, s2: Оригінальні рядки
            consonants1, consonants2: Приголосні з рядків
            
        Returns:
            Схожість від 0.0 до 1.0
        """
        if not consonants1 or not consonants2:
            # Якщо немає приголосних, використовуємо загальну схожість
            return SimilarityCalculator.jaro_winkler_similarity(s1, s2) * 0.5
        
        return SimilarityCalculator.jaro_winkler_similarity(consonants1, consonants2)
